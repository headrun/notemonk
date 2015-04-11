from __future__ import with_statement
import os
import re
import datetime
from cStringIO import StringIO
from itertools import chain
import hashlib

import Image as PIL
import simplejson as json

from django.core.urlresolvers import reverse
from django import template
from django.template import Context
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.contrib.contenttypes.models import ContentType
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
#from pure_pagination import Paginator, InvalidPage, EmptyPage
#from flynsarmy_paginator.paginator import FlynsarmyPaginator
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core.files.base import ContentFile
from django.db import IntegrityError, connection
from django.db.models.query import QuerySet
from django.db.models import Q
from django.conf import settings
from django.core.files.uploadhandler import TemporaryFileUploadHandler


from reversion import revision
from reversion.models import Version
import notification.models as notification
from notification.models import NoticeSetting, NoticeType
import facebook.djangofb as facebook
from django.core.mail import send_mail

from models import *
from utils import get_doc, xcode, sanitize_whitespace, urlsafe, get_md5
from utils import get_target, get_target_from_req, QuerySetFilter, QuerySetMerge
from forms import LoginForm, UserProfileForm, FeedbackForm, InviteForm
from forms import AddBookForm, EditBookForm, MailingAddressForm
from forms import make_notifications_form, EmailForm
from query import load_videos, get_items_by_tag, get_top_users
from points import give_points

ITEMS_PER_PAGE = 10
WALL_ITEMS_PER_PAGE = 25
REVISIONS_PER_PAGE = 10
POINT_HISTORY_PER_PAGE = 10
DEFAULT_PAGE_TITLE = 'Notemonk - A brand new way to experience your books.'
PTITLE = '%s - Notemonk'

def render_response(req, template, data=None):
    data = data or {}
    r = RequestContext(req)

    data['ref_path'] = req.get_full_path()
    if 'page_title' not in data:
        data['page_title'] = DEFAULT_PAGE_TITLE

    return render_to_response(template, data, context_instance=r)

def render_error(request, message):
    return render_response(request, 'ui/base.html',
                   {'error': message})

def custom_login_required(fn):
    def login_req(request, *args, **kwargs):
        next = request.POST['ref_path'] if 'ref_path' in request.POST \
                                            else ''
        if not next:
                next = request.get_full_path()

        if not request.user.is_authenticated():
            return HttpResponseRedirect('/login/?next=%s' % next)

        if not request.user.email:
            return HttpResponseRedirect('/email/?next=%s' % next)

        return fn(request, *args, **kwargs)
    return login_req

def ensure_no_mem_file(fn):
    def wrapper(request, *args, **kwargs):
        request.upload_handlers = [TemporaryFileUploadHandler()]
        return fn(request, *args, **kwargs)
    return wrapper

def ncert_view(request):
    page_title = PTITLE % 'Download NCERT Books'
    return render_response(request, 'ui/groups/ncert.html', {
                           'page_title': page_title})

def tamilnadu_view(request):
    page_title = PTITLE % 'Download Tamilnadu Books'
    return render_response(request, 'ui/groups/tamilnadu.html', {
                           'page_title': page_title})

def bits_view(request):
    page_title = PTITLE % 'Download BITS MSSS Books'
    return render_response(request, 'ui/groups/bits_msss.html', {
                           'page_title': page_title})
def anu_view(request):
    page_title = PTITLE % 'Download Acharya Nagarjuna University (ANU) Books'
    return render_response(request, 'ui/groups/anu_books.html', {
                           'page_title': page_title})

def ipe_view(request):
    page_title = PTITLE % 'Download Andhra Pradesh Intermediate Books'
    return render_response(request, 'ui/groups/ipe_books.html', {
                           'page_title': page_title})
def cbse_view(request):
    page_title = PTITLE % 'Download CBSE Books'
    return render_response(request, 'ui/groups/cbse_books.html', {
                           'page_title': page_title})

def aieee_view(request):
    page_title = PTITLE % 'Download AIEEE Books'
    return render_response(request, 'ui/groups/aieee_books.html', {
                           'page_title': page_title})
def iitjee_view(request):
    page_title = PTITLE % 'Download IITJEE Books'
    return render_response(request, 'ui/groups/iitjee_books.html', {
                           'page_title': page_title})
def upsc_view(request):
    page_title = PTITLE % 'Download UPSC Books'
    return render_response(request, 'ui/groups/upsc_books.html', {
                           'page_title': page_title})
def privacy_policy_view(request):
    page_title = "Privacy Policy"
    return render_response(request, 'ui/privacy_policy.html', {
                            'page_title': page_title})

# background ad [ bad.html ]
def bad_view(request):
    page_title = PTITLE % 'Background ad'
    return render_response(request, 'ui/bad.html', {
                           'page_title': page_title})


def get_followers(*objects):
    objects = [get_root(o) for o in objects]
    objects = [o for o in objects if o]
    followers = set(chain(*[[f.user for f in o.followers.all()] for o in objects]))

    superusers_notify = getattr(settings, 'SUPERUSERS_NOTIFY', False)
    if superusers_notify:
        superusers = User.objects.filter(is_superuser=True)
        followers.update(superusers)

    return list(followers)

def get_root(object):
    target = object

    while target:
       if hasattr(target, 'follow'):
           return target

       target = getattr(target, 'target', None)

def follow_root(target, user):
    root = get_root(target)
    if root:
        return root.follow(user)

def add_to_book_stream(target, activity):
    root = get_root(target)
    return root.stream.add(activity) if root and isinstance(root, Book) else None

def make_paginator(queryset, page_no, num):
    page_no = page_no or 1
    num = num or ITEMS_PER_PAGE
    paginator = Paginator(queryset, int(num))
    try:
        paginator = paginator.page(int(page_no))
    except (EmptyPage, InvalidPage):
        paginator = paginator.page(paginator.num_pages)

    return paginator

def login_view(request):
    top_users = get_top_users()

    next = ''
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            next = request.POST['ref_path'] if 'ref_path' in request.POST \
                                            else ''

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            persistent = form.cleaned_data['persistent']

            if not persistent:
                request.session.set_expiry(0)

            user = authenticate(username=username, password=password)
            if user:
                if user.is_active:
                    login(request, user)
                else:
                    return render_response(request, 'ui/login.html', {
                                           'next': next,
                                           'form': form,
                                           'top_users': top_users,
                                           'avoid': True,
                                           'error': "Your account is de-activated"
                                           })

            else:
                return render_response(request, 'ui/login.html', {
                                       'next': next,
                                       'form': form,
                                       'top_users': top_users,
                                       'avoid': True,
                                       'error': "Your Username or Password was incorrect"
                                       })

            return HttpResponseRedirect(next or reverse('home_page'))
    else:
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('home_page'))

        next = request.GET['next'] if 'next' in request.GET else ''
        form = LoginForm()

    return render_response(request, 'ui/login.html', {
                           'next': next,
                           'form': form,
                           'top_users': top_users,
                           'avoid': True,
                           'page_title': PTITLE % 'Login'
                           })

def logout_user(request):
    logout(request)
    return HttpResponseRedirect(reverse('home_page'))

@login_required
def email_view(request):
    next = ''
    email = ''
    error = ''

    top_users = get_top_users()

    if request.method == 'POST':
        form = EmailForm(request.POST)
        next = request.POST['ref_path']

        if form.is_valid():
            email = form.cleaned_data['email']
            re_enter_email = form.cleaned_data['re_enter_email']
            if email != re_enter_email:
                error = 'Please re-enter email correctly'
                return render_response(request, 'ui/email.html',
                           {'form': form,
                            'next': next,
                            'top_users': top_users,
                            'error': error,
                           'page_title': PTITLE % 'Email'})

            request.user.email = email
            request.user.save()

            return HttpResponseRedirect(next or reverse('home_page'))
    else:
        form = EmailForm()
        next = request.GET['next'] if 'next' in request.GET else ''

        error = 'Hi Facebook user, please enter your email-id below.'

    return render_response(request, 'ui/email.html',
                           {'form': form,
                            'next': next,
                            'top_users': top_users,
                            'error': error,
                           'page_title': PTITLE % 'Email'})

def _filter_stream(filter, user):
    filter_str = '' if filter == 'activities' else filter + '/'
    paging_url = '/user/%s/%s<PAGENO>/' % (user.username, filter_str)
    use_target = False
    as_wall = False

    page_title = PTITLE % ('%s of %s' % (filter.capitalize(), user.get_profile().title))

    if filter == 'notes':
        stream = Note.objects.filter(user=user)
    elif filter == 'videos':
        stream = AssociatedMedia.objects.filter(user=user)
        as_wall = True
    elif filter == 'questions':
        stream = user.get_profile().questions
    elif filter == 'answers':
        stream = user.get_profile().answers
    elif filter == 'books':
        stream = user.get_profile().books
        as_wall = True
    elif filter == 'fbooks':
        stream = user.get_profile().following_books
        as_wall = True
    elif filter == 'followers':
        stream = user.get_profile().followers.all()
        stream = QuerySetFilter(stream, lambda x: x.user.get_profile())
        as_wall = True
    elif filter == 'following':
        stream = user.get_profile().following
        as_wall = True
    elif filter == 'referred':
        stream = user.get_profile().referred
        as_wall = True
    elif filter == 'comments':
        stream = user.get_profile().comments
    elif filter == 'points':
        stream = user.get_profile().points_history

    return stream, paging_url, use_target, as_wall, page_title

def user_items_view(request, username=None, page_no=1, num=None, filter=None):

    try:
        username = username or request.user.username
        page_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return render_response(request, 'ui/base.html', {'error': 'User not known'})

    stream, paging_url, use_target, as_wall, page_title = _filter_stream(filter, page_user)
    stream = make_paginator(stream, page_no, num)

    num = WALL_ITEMS_PER_PAGE if as_wall else ITEMS_PER_PAGE
    template = 'ui/user_wall.html' if as_wall else 'ui/user_items.html'

    return render_response(request, template,
                           {'page_user': page_user,
                           'page_title': page_title,
                           'stream': stream,
                           'paging_url': paging_url,
                           'use_target': use_target})

def _get_activity_stream(request, page_user, a_id):

    book_streams = []

    if page_user == request.user:
        users = [page_user] + [x.user for x in page_user.get_profile().following]

        # dont show Notemonk's activities to followers (too many items)
        if page_user.id != 1:
            users = [u for u in users if u.id != 1]

        stream = Activity.objects.filter(user__in=users)

        for b in page_user.get_profile().following_books:
            bstream = StreamItem.objects.filter(stream=b.stream).order_by('-id')

            if a_id is not None:
                bstream = bstream.filter(activity__lte=a_id)

            bstream = QuerySetFilter(bstream, lambda x: x.activity)
            book_streams.append(bstream)

    else:
        stream = Activity.objects.filter(user=page_user)

    # activities associated with user
    user_stream = page_user.get_profile().stream
    user_stream = StreamItem.objects.filter(stream=user_stream)

    if a_id is not None:
        stream = stream.filter(id__lte=a_id)
        user_stream = user_stream.filter(activity__lte=a_id)

    user_stream = QuerySetFilter(user_stream, lambda x: x.activity)
    streams = [stream, user_stream]
    streams.extend(book_streams)

    stream = QuerySetMerge(streams, '-id')

    return stream

def _find_slot(slots, activity):
    MAX_ITEMS_PER_SLOT = 8
    MAX_TIMEDIFF = 3600 #seconds or 1 hour

    dt = activity.date_added
    target = activity.target

    for index, s in enumerate(reversed(slots)):
        s_target = s['target']
        s_dt = s['dt']
        s_items = s['items']

        if len(s_items) >= MAX_ITEMS_PER_SLOT and\
            not isinstance(target, Comment):
            continue

        if index != 0:
            tdiff = max(dt, s_dt) - min(dt, s_dt)
            tdiff = tdiff.seconds
            if tdiff > MAX_TIMEDIFF:
                continue

        if isinstance(target, PointsHistory):
            if isinstance(s_target, PointsHistory):
                return s

        elif isinstance(target, Ratings):
            if isinstance(s_target, Ratings):
                return s

        elif isinstance(target, Comment):
            ctarget = target.target
            if ctarget == s_target:
                return s

        elif isinstance(target, ProfilePost):
            if target == s_target:
                return s

    # slot not found for comment, so create slot
    if isinstance(target, Comment):
        slots.append({'target': target.target, 'dt': activity.date_added, 'items': []})
        return slots[-1]

def _make_stream_from_slots(slots):
    stream = []

    for s in slots:
        items = s['items']
        if len(items) == 1:
            stream.append(items[0])

        else:
            stream.append(ItemGroup(items))

    return stream

def _digest_activity_stream(stream, num_items=ITEMS_PER_PAGE):

    next_id = None
    slots = []

    activities_seen = set()

    counter = 0
    for a in stream[:100]:
        if a.id in activities_seen:
            continue
        activities_seen.add(a.id)

        counter += 1
        next_id = a.id - 1

        slot = _find_slot(slots, a)
        if slot:
            if slot['target'] != a.target:
                slot['items'].append(a)
        else:
            slot = {'target': a.target,
                    'dt': a.date_added,
                    'items': [a]}
            slots.append(slot)

        if len(slots) >= num_items:
            break

    stream = _make_stream_from_slots(slots)

    return stream, next_id

def user_view(request, username=None, a_id=None):

    try:
        username = username or request.user.username
        page_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return render_response(request, 'ui/base.html', {'error': 'User not known'})

    stream = _get_activity_stream(request, page_user, a_id)
    stream, next_id = _digest_activity_stream(stream)

    if a_id is None:
        page_title = PTITLE % ('%s' % page_user.get_profile().title)
    else:
        page_title = PTITLE % ('Activities of %s' % page_user.get_profile().title)

    return render_response(request, 'ui/user_activities.html',
                           {'page_user': page_user,
                           'page_title': page_title,
                           'stream': stream,
                           'next_id': next_id})

def activities_view(request, a_id=None):

    stream = Activity.objects.all()
    stream = stream.filter(id__lte=a_id) if a_id is not None else stream
    stream = stream.order_by('-id')
    stream, next_id = _digest_activity_stream(stream)

    page_title = PTITLE % 'Activities of Notemonkers'

    return render_response(request, 'ui/activities.html',
                           {'page_title': page_title,
                           'stream': stream,
                           'next_id': next_id})

class PermissionException(Exception):
    pass

@login_required
def user_edit_view(request):

    error = ''

    try:
        page_user = User.objects.get(username=request.user.username)
        profile = page_user.get_profile()

        mapping = (
                   ('first_name', page_user),
                   ('last_name', page_user),
                   ('email', page_user),
                   ('institution', profile),
                   ('city', profile),
                   ('state', profile),
                   ('country', profile),
                   ('mailing_address', profile),
                   ('dob', profile),
                   ('sex', profile),
                   )

    except User.DoesNotExist:
        error = 'User not found'

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        nform = make_notifications_form(request.POST)

        if form.is_valid():

            for field, target in mapping:
                setattr(target, field, form.cleaned_data[field])

            password = form.cleaned_data['password1']

            if password:
                page_user.set_password(password)

            image = request.FILES.get('image')
            if image:
                cfile = ContentFile(image.read())
                profile.image.save(image.name, cfile, save=True)

            page_user.save()
            profile.save()

            # notification form processing
            for n in NoticeType.objects.all():

                if n.label.startswith('_'):
                    continue

                value = bool(request.POST[n.label] if n.label in request.POST \
                                            else False)

                try:
                    ns = NoticeSetting.objects.create(user=page_user,
                            notice_type=n, medium='1',
                            send=value)
                except IntegrityError:
                    ns = NoticeSetting.objects.get(user=page_user,
                            notice_type=n, medium='1')
                    ns.send = value
                    ns.save()

            followers = get_followers(profile)
            notification.send(followers, 'profile_changed', {'user': page_user})

            return HttpResponseRedirect(reverse('user_page',
                                        kwargs={'username': page_user.username}))
    else:
        data = dict([(field, getattr(source, field)) for field, source in mapping])
        form = UserProfileForm(data)

        data = {}
        for n in NoticeType.objects.all():
            try:
                ns = NoticeSetting.objects.get(user=page_user,
                        notice_type=n, medium='1')
                value = ns.send
            except ObjectDoesNotExist:
                value = True

            data[n.label] = value

        nform = make_notifications_form(data)

    return render_response(request, 'ui/user_edit.html',
                           {'page_user': page_user,
                           'error': error,
                           'form': form,
                           'nform': nform,
                           'page_title': PTITLE % ('%s - Edit' % page_user.get_profile().title)})

def home_view(request):
    #new_notes = Note.objects.order_by('-date_added').\
    #                exclude(target_type=\
    #                    ContentType.objects.get_for_model(UserProfile))

    popular_books = Book.objects.order_by('-tot_count')[:5]

    new_videos = AssociatedMedia.objects.filter(media_type=\
                        ContentType.objects.get_for_model(Video)).order_by('-id')[:10]

    #new_questions = Question.objects.order_by('-date_added')

    #active_users = LeaderBoardData.objects.filter(tag='active',\
    #                target_type=ContentType.objects.get_for_model(UserProfile))

    top_users = get_top_users()

    #active_topics = LeaderBoardData.objects.filter(tag='active',\
    #                target_type=ContentType.objects.get_for_model(Node))

    stream = Activity.objects.order_by('-id')[:50]
    stream, next_id = _digest_activity_stream(stream, 20)

    #one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    #sql_datetime = datetime.datetime.strftime(one_hour_ago, '%Y-%m-%d %H:%M:%S')
    #online_users = User.objects.filter(last_login__gt=sql_datetime,
    #                            is_active__exact=1).order_by('-last_login')[:10]

    online_users = Onliners.objects.order_by('id')
    online_users = [o.user for o in online_users]

    return render_response(request, 'ui/home.html',
                           {#'new_notes': new_notes,
                            'popular_books': popular_books,
                            #'new_videos': new_videos,
                            'top_users': top_users,
                            #'active_users': active_users,
                            #'active_topics': active_topics,
                            'online_users': online_users,
                            #'new_questions': new_questions,
                            'stream': stream, 'next_id': next_id})

def load_media(contentmodel):
    core = User.objects.get(id=1)

    #if not contentmodel.images:
        #    load_images(contentmodel, core)

    if not contentmodel.videos:
        load_videos(contentmodel, core)

def book_view(request, book_id):
    try:
        book = Book.objects.get(id=book_id)
    except ObjectDoesNotExist:
        return render_response(request, 'ui/base.html',
                               {'error': 'Could not locate the book. Sorry.'})

    is_editable = book.is_editable_by(request.user)

    return render_response(request, 'ui/book.html',
                           {'book': book,
                            'is_editable': is_editable,
                            'subtopics': book.node_set.filter(parent=None).order_by('order'),
                            'page_title': PTITLE % ('Book - %s' % book.title)})

@custom_login_required
def book_add_view(request):

    if not request.user.get_profile().can_add_book:
        return render_response(request, 'ui/base.html',
            {'error': 'You cannot add a new book'})

    tags = []

    if request.method == 'POST':
        form = AddBookForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            isbn = form.cleaned_data['isbn']
            tags = form.cleaned_data['tags']

            default_image = os.path.join(settings.MEDIA_ROOT, 'images/book_generic.gif')
            default_image = os.path.normpath(default_image)
            cfile = ContentFile(open(default_image, 'rb').read())

            book = Book.objects.create(title=title, isbn=isbn, user=request.user)
            stream = Stream.objects.create(title='for book: %s' % book.title)
            book.stream = stream

            Activity.add(request.user, book)

            tags = Tag.objects.filter(id__in=tags)
            for t in tags:
                book.tags.create(tag=t)

            book.cover_image.save('%d_default_book.gif' % book.id, cfile, save=True)
            book.follow(request.user)
            book.rate_up(request.user)
            book.save()

            Node.objects.create(title='New topic', book=book,
                                parent=None, order=0)

            return HttpResponseRedirect(reverse('book_edit_page',
                                        kwargs={'book_id': book.id}))
    else:
        form = AddBookForm()

    return render_response(request, 'ui/book_add.html',
            {'form': form, 'page_title': PTITLE % ('Add book')})

@custom_login_required
def book_edit_view(request, book_id):

    try:
        book = Book.objects.get(id=book_id)
    except ObjectDoesNotExist:
        return render_response(request, 'ui/base.html',
                               {'error': 'Could not locate the book. Sorry.'})

    is_editable = request.user.get_profile().can_edit_book(book)
    if not is_editable:
        return render_response(request, 'ui/base.html',
            {'error': 'You cannot edit this book'})

    data = {'title': book.title, 'isbn': book.isbn,
            'tags': '', 'moderators': ''}
    form = EditBookForm(initial=data)

    if request.method == 'POST':
        if 'outline_data' in request.POST:
            book.update_json(request.POST['outline_data'])

        else:
            form = EditBookForm(request.POST)
            if form.is_valid():
                title = form.cleaned_data['title']
                isbn = form.cleaned_data['isbn']
                tags = form.cleaned_data['tags']
                moderators = form.cleaned_data['moderators']

                # process tags
                book.tags.all().delete()
                tags = Tag.objects.filter(id__in=tags)
                for t in tags:
                    book.tags.create(tag=t)

                # process moderators
                for m in book.moderators.all():
                    book.moderators.remove(m)

                moderators = User.objects.filter(id__in=moderators)
                for m in moderators:
                    book.moderators.add(m)

                # process image
                image = request.FILES.get('image')
                if image:
                    cfile = ContentFile(image.read())
                    book.cover_image.save(image.name, cfile, save=True)

                book.title = title
                book.isbn = isbn
                book.save()

    tags = [{'id': t.tag.id, 'name': t.tag.name} for t in book.tags.all()]
    tags = json.dumps(tags)

    moderators = [{'id': m.id, 'name': m.get_profile().title}\
                    for m in book.moderators.all()]
    moderators = json.dumps(moderators)

    return render_response(request, 'ui/book_edit.html',
                           {'book': book,
                            'tags': tags,
                            'moderators': moderators,
                            'form': form,
                            'page_title': PTITLE % ('Book Edit - %s' % book.title)})

def book_moderators_view(request, book_id, page_no=1, num=ITEMS_PER_PAGE):

    try:
        book = Book.objects.get(id=book_id)
    except ObjectDoesNotExist:
        return render_response(request, 'ui/base.html',
                       {'error': 'Could not locate the book. Sorry.'})

    moderators = book.moderators.all()
    moderators = make_paginator(moderators, page_no, num)
    paging_url = '/book/moderators/%s/<PAGENO>/' % (book.id)

    title ='Moderators for book: %s' % (book.title)
    page_title = PTITLE % (title)

    return render_response(request, 'ui/users.html',
                           {'users': moderators,
                           'page_title': page_title,
                           'title': title,
                           'paging_url': paging_url})

@custom_login_required
def book_request_moderation_view(request, book_id):

    try:
        book = Book.objects.get(id=book_id)
    except ObjectDoesNotExist:
        return render_response(request, 'ui/base.html',
                       {'error': 'Could not locate the book. Sorry.'})

    notification.send([book.user], 'book_mod_request',
        {'user': request.user, 'book': book})

    page_title = PTITLE % ('Book moderation request sent')
    return render_response(request, 'ui/book_request_moderation.html',
                           {'owner': book.user,
                           'page_title': page_title,
                           'book': book})

@custom_login_required
def book_confirm_moderation_view(request, book_id, username):
    try:
        book = Book.objects.get(id=book_id)
    except ObjectDoesNotExist:
        return render_error(request, 'Could not locate the book. Sorry.')

    if request.user != book.user:
        return render_error(request, 'You are not the owner of this book.')

    try:
        user = User.objects.get(username=username)
    except ObjectDoesNotExist:
        return render_error(request, 'User "%s" not known' % username)

    book.moderators.add(user)

    page_title = PTITLE % ('Book moderation request accepted')
    return render_response(request, 'ui/book_moderation_accepted.html',
                           {'moderator': user,
                           'page_title': page_title,
                           'book': book})

def books_view(request):
    return HttpResponseRedirect(reverse('books_recent_page'))

def books_recent_view(request, page_no=1, num=ITEMS_PER_PAGE):
    books = Book.objects.all().order_by('-date_added')
    books = make_paginator(books, page_no, num)
    paging_url = '/books/recent/<PAGENO>/'
    page_title = PTITLE % ('Recently Added Books')
    return render_response(request, 'ui/books_list.html',
        {'books': books, 'page_title': page_title,
         'paging_url': paging_url})

def books_popular_view(request, page_no=1, num=ITEMS_PER_PAGE):
    books = Book.objects.all().order_by('-tot_count')
    books = make_paginator(books, page_no, num)
    paging_url = '/books/popular/<PAGENO>/'
    page_title = PTITLE % ('Most Popular Books')
    return render_response(request, 'ui/books_list.html',
        {'books': books, 'page_title': page_title, 'paging_url': paging_url})

def books_tag_view(request, tag, page_no=1, num=ITEMS_PER_PAGE):
    books = get_items_by_tag(Book, [tag], 'all')
    books = make_paginator(books, page_no, num)
    paging_url = '/books/tag/%(tag)s/<PAGENO>/' % locals()
    page_title = PTITLE % ('Books tagged "%s"' % tag)
    return render_response(request, 'ui/books_list.html',
        {'books': books, 'page_title': page_title, 'paging_url': paging_url})

def books_tag_all_view(request, tags, page_no=1, num=ITEMS_PER_PAGE):
    paging_url = '/books/tag/all/%(tags)s/<PAGENO>/' % locals()
    tags = [t.strip() for t in tags.split('/') if t.strip()]
    books = get_items_by_tag(Book, tags, 'all')
    books = make_paginator(books, page_no, num)
    page_title = PTITLE % ('Books tagged "%s"' % ', '.join(tags))
    return render_response(request, 'ui/books_list.html',
        {'books': books, 'page_title': page_title, 'paging_url': paging_url})

def books_tag_any_view(request, tags, page_no=1, num=ITEMS_PER_PAGE):
    paging_url = '/books/tag/any/%(tags)s/<PAGENO>/' % locals()
    tags = [t.strip() for t in tags.split('/') if t.strip()]
    books = get_items_by_tag(Book, tags, 'any')
    books = make_paginator(books, page_no, num)
    page_title = PTITLE % ('Books tagged with one of "%s"' % ', '.join(tags))
    return render_response(request, 'ui/books_list.html',
        {'books': books, 'page_title': page_title, 'paging_url': paging_url})

def tags_view(request):
    term = request.GET['q'].lower()

    query = 'SELECT id, name FROM core_tag WHERE LOWER(name) LIKE %s ORDER BY name'
    cursor = connection.cursor()
    cursor.execute(query, ('%'+term+'%',))

    tags = [dict(id=_id, name=name) for _id, name in cursor.fetchall()]

    if 'callback' in request.GET:
        response = '%s(%s)' % (request.GET['callback'], json.dumps(tags))
    else:
        response = json.dumps(tags)

    return HttpResponse(response, mimetype='application/json')

def node_view(request, node_id):
    try:
        node = Node.objects.get(id=node_id)
        load_media(node)
    except ObjectDoesNotExist:
        return render_response(request, 'ui/node.html', {
                               'error': 'no node with id %s' % node_id})

    bread_crumbs = build_breadcrumbs(node)

    return render_response(request, 'ui/node.html', {
                           'node': node,
                           'bread_crumbs': bread_crumbs,
                           'page_title': PTITLE % ('Topic - %s' % node.title)}
                           )

def build_breadcrumbs(node):
    s = StringIO()
    parents = []

    parents.append(('/node/%s/%s/' % (node.id, urlsafe(node.title)),
                   xcode(node.title)))

    while node.parent:
        node = node.parent
        parents.append(('/node/%s/%s/' % (node.id, urlsafe(node.title)),
                       xcode(node.title)))

    parents.append(('/book/%s/%s/' % (node.book.id, urlsafe(node.book.title)),
                   xcode(node.book.title)))

    while parents:
        url, title  = parents.pop()
        s.write('<a href="%s">%s</a>' % (url, title))
        if parents:
            s.write(' > ')

    return s.getvalue()

def note_view(request, note_id):

    note = Note.objects.get(id=note_id)
    page_title = PTITLE % ('Notes for %s' % note.target.title)

    return render_response(request, 'ui/note.html', {
                           'note': note, 'page_title': page_title})

@custom_login_required
def note_edit_view(request, note_id, page_no=1, num=ITEMS_PER_PAGE):

    note = Note.objects.get(id=note_id)
    versions = Version.objects.get_for_object(note).reverse()

    if 'note' in request.POST:

        redirect_url = xcode(request.POST['content_path'])
        if not request.POST['note'] and not versions:
            note.delete()
            return HttpResponseRedirect(redirect_url)

        with revision:
            note.text.raw = request.POST['note']
            note.save()

            revision.user = request.user
            revision.comment = request.POST['comment'] or 'update'

        followers = get_followers(note, note.target,
                                  request.user.get_profile())
        notification.send(followers, 'note_changed', {'user': request.user,
                                                      'note': note})


        return HttpResponseRedirect(redirect_url)

    else:

        versions = make_paginator(versions, page_no, num)
        paging_url = '/note/%s/revisions/<PAGENO>/' % note.id
        page_title = PTITLE % ('Notes for %s' % note.target.title)

        return render_response(request, 'ui/note_edit.html',
                               {'note': note, 'versions': versions,
                                'page_title': page_title,
                                'paging_url': paging_url})

def note_revision_view(request, note_id, revision_id):
    note = Note.objects.get(id=note_id)
    version = Version.objects.get(id=revision_id)
    page_title = PTITLE % ('Note Revision for %s' % note.target.title)

    return render_response(request, 'ui/revision.html',
                           {'version': version, 'note': note, 'page_title': page_title})

@custom_login_required
def note_revision_revert_view(request, note_id, revision_id):
    version = Version.objects.get(id=revision_id)
    note = Note.objects.get(id=note_id)

    with revision:
        note.text.raw = version.field_dict['text']
        note.save()

        revision.user = request.user
        revision.comment = 'reverting to revision number %d' % version.id

    return HttpResponseRedirect(request.POST['ref_path'])

def video_view(request, avideo_id):
    amedia = None

    try:
        avideo = AssociatedMedia.objects.get(id=avideo_id)
        title = avideo.media.title

    except ObjectDoesNotExist:
        #return render_response(request, 'ui/video.html',
        #                       {'error': 'no video with id %s' % video_id})

        #Added on 11-10-2013 by Yatish(to handle error condition if video is not present)
        #return HttpResponseRedirect(reverse('home_page'))
        #data = render_to_response(request, 'ui/404.html')
        data = render_response(request, 'ui/404.html')
        return HttpResponse(data.content, status=410)

    return render_response(request, 'ui/video.html',
                           {'avideo': avideo,
                           'page_title': PTITLE % ('Video for %s' % title)})

def videos_view(request, target_type, target,
                page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    videos = make_paginator(target.videos, page_no, num)
    paging_url = '/videos/%s/%s/<PAGENO>/%s/' % (target.ctype.id,
                    target.id, target.title)

    return render_response(request, 'ui/videos.html',
                           {'target': target, 'videos': videos,
                           'page_title': PTITLE % ('Videos for %s' % target.title),
                           'paging_url': paging_url})

def image_view(request, image_id):
    try:
        image = Image.objects.get(id=image_id)
        args = {'image': image}
    except ObjectDoesNotExist:
        args = {'error': 'no image with id %s' % image_id}

    # FIXME: args['page_title'] = PTITLE
    return render_response(request, 'ui/image.html', args)

def images_view(request, target_type, target,
                page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    images = make_paginator(target.images, page_no, num)

    # FIXME: compute page title and pass to template as page_title
    return render_response(request, 'ui/images.html',
                           {'target': target, 'images': images})

def notes_view(request, target_type, target, page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    notes = make_paginator(target.notes, page_no, num)
    paging_url = '/notes/%s/%s/<PAGENO>/' % (target.ctype.id, target.id)
    page_title = PTITLE % ('Notes for %s' % target.title)

    return render_response(request, 'ui/notes.html',
                           {'target': target, 'notes': notes,
                           'page_title': page_title,
                           'paging_url': paging_url})

def get_yt_id(yt_url):
    query_part = yt_url.split('?')[-1]
    parts = query_part.split('&')
    for p in parts:
        if p.startswith('v='):
            return p.split('v=')[-1]
    return None

def get_ytvideo_title(yt_id):
    api = 'http://gdata.youtube.com/feeds/api/videos/%s'
    url = api % yt_id

    text = get_doc(url, settings.CACHE_DIR)
    title = re.findall('<title.*?>(.*?)</title>', text)
    if title:
        return title[0].decode('utf8', 'ignore')
    return None

@custom_login_required
def add_video(request):
    user = request.user

    video_url = request.POST['video_url']
    target = get_target_from_req(request)

    yt_id = get_yt_id(video_url)

    if not yt_id:
        return HttpResponseRedirect(request.POST['ref_path'])

    title = get_ytvideo_title(yt_id)

    try:
        video = Video.objects.create(source='youtube', source_id=yt_id,
                                     user=user, title=title)
    except IntegrityError:
        video = Video.objects.get(source='youtube', source_id=yt_id)

    try:
        avideo = AssociatedMedia.add(user=user, target=target, media=video)
        avideo.rate_up(user)
        avideo.save()
        follow_root(avideo, user)

        give_points('video_add', user=user.id, avideo=avideo.id)
        ac = Activity.add(user, avideo)
        add_to_book_stream(avideo, ac)

        followers = get_followers(video, user.get_profile())
        notification.send(followers, 'video_add', {'user': user,
                                                   'video': video})
    except IntegrityError:
        pass

    return HttpResponseRedirect(request.POST['ref_path'])

@custom_login_required
def add_image(request):
    user = request.user

    target_type = request.POST['target_type']
    target = request.POST['target']
    image_url = request.POST['image_url']

    target_type = ContentType.objects.get(id=int(target_type))
    target = content_type.get_object_for_this_type(id=int(target))
    target = get_target_from_req(request)

    #TODO Integrity check has to be done
    image = Image.objects.create(url=image_url, user=user)
    aimage = AssociatedMedia.add(user=user, target=target, media=image)
    aimage.rate_up(user)
    aimage.save()
    follow_root(aimage, user)

    return HttpResponseRedirect(request.POST['ref_path'])

@custom_login_required
def add_note(request):
    user = request.user
    target = get_target_from_req(request)

    note = Note.add(target, user=user)
    note.rate_up(user)
    note.save()
    follow_root(note, user)

    give_points('note_add', user=user.id, note=note.id)
    ac = Activity.add(user, note)
    add_to_book_stream(note, ac)

    return HttpResponseRedirect(reverse('note_edit_page', args=(note.id,)))

@custom_login_required
def question(request):
    user = request.user
    q_text = request.POST['question_text']
    if not q_text:
        return HttpResponseRedirect(request.POST['ref_path'])

    target = get_target_from_req(request)
    question = Question.add(user, target, q_text)
    question.rate_up(user)
    question.save()
    follow_root(question, user)

    ac = Activity.add(user, question)
    add_to_book_stream(question, ac)
    give_points('question_add', user=user.id, question=question.id)

    followers = get_followers(target, user.get_profile())
    notification.send(followers, 'question_add', {'user': user,
                                                  'question': question})

    return HttpResponseRedirect(request.POST['ref_path'])

@custom_login_required
def answer(request):
    user = request.user

    q_id = request.POST['q_id']
    a_text = sanitize_whitespace(request.POST['answer_text'])
    if not a_text:
        return HttpResponseRedirect(request.POST['ref_path'])

    question = Question.objects.get(id=q_id)
    answer = Answer.objects.create(user=user, question=question, text=a_text)
    answer.rate_up(user)
    answer.save()
    question.save()
    follow_root(question, user)

    ac = Activity.add(user, answer)
    if question.user != user:
        question.user.get_profile().stream.add(ac)
    add_to_book_stream(answer, ac)

    give_points('answer_add', user=user.id, answer=answer.id)

    followers = get_followers(question,
                              question.target,
                              user.get_profile())
    notification.send(followers, 'answer_add', {'user': user, 'answer': answer,
                                                'question': question})

    return HttpResponseRedirect(request.POST['ref_path'])

def question_view(request, q_id):
    question = Question.objects.get(id=q_id)
    answer_text_id = 'answer_text_%d_%d' % (question.ctype.id, question.id)
    page_title = PTITLE % ('Question: %s' % question.text.raw)

    return render_response(request, 'ui/question.html', {
                           'question': question, 'page_title': page_title,
                           'answer_text_id': answer_text_id})

def questions_view(request, target_type, target,
                   page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    questions = make_paginator(target.questions.all(), page_no, num)
    paging_url = '/questions/%s/%s/<PAGENO>/' % (target.ctype.id, target.id)
    page_title = PTITLE % ('Questions for %s' % target.title)

    return render_response(request, 'ui/questions.html', {
                           'target': target,
                           'questions': questions,
                           'page_title': page_title,
                           'paging_url': paging_url}
                           )

@custom_login_required
def rate(request):
    user = request.user

    rating = request.POST['rating']
    target = get_target_from_req(request)

    rate_obj = target.rate_up(user) if rating == 'up' else target.rate_down(user)
    target.save()

    if rate_obj:
        ac = Activity.add(user, rate_obj)

        if target.user != user:
            target.user.get_profile().stream.add(ac)
        add_to_book_stream(target, ac)

    follow_root(target, user)

    followers = get_followers(target, user.get_profile())

    template_variables = {'user': user, 'rate_obj': target, 'rating': rating}
    fn = lambda n: notification.send(followers, n, template_variables)

    if isinstance(target, Question):
        fn('question_rated')
    elif isinstance(target, Answer):
        fn('answer_rated')
    elif isinstance(target, UserProfile):
        fn('profile_rated')
    elif isinstance(target, Note):
        fn('note_rated')
    elif isinstance(target, AssociatedMedia):
        fn('video_rated')
    elif isinstance(target, Book):
        fn('book_rated')
    elif isinstance(target, Node):
        fn('node_rated')

    return HttpResponseRedirect(request.POST['ref_path'])

@custom_login_required
def follow(request):
    user = request.user

    follow = request.POST['follow']
    target = get_target_from_req(request)
    follow_obj = target.follow(user) if follow == 'follow' else target.unfollow(user)
    target.save()

    if follow_obj:
        ac = Activity.add(user, follow_obj)

        if target.user != user:
            target.user.get_profile().stream.add(ac)
        add_to_book_stream(target, ac)

    return HttpResponseRedirect(request.POST['ref_path'])

@custom_login_required
def flag(request):
    user = request.user

    flag = request.POST['flag']
    target = get_target_from_req(request)
    flag_obj = target.flag(user) if flag == 'flag' else target.unflag(user)
    target.save()

    if flag_obj:
        ac = Activity.add(user, flag_obj)

        if target.user != user:
            target.user.get_profile().stream.add(ac)
        add_to_book_stream(target, ac)

    return HttpResponseRedirect(request.POST['ref_path'])

def feedback_view(request):
    name = ''
    email = ''

    if request.user.is_authenticated():
        name = request.user.get_profile().title
        email = request.user.email

    if request.method == 'POST':
        form = FeedbackForm(request.POST)

        if form.is_valid():

            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            feedback = form.cleaned_data['feedback']

            followers = User.objects.filter(is_superuser=True)
#            import pdb; pdb.set_trace()
            notification.send(followers, '_user_feedback',
                              {'user': request.user, 'feedback': feedback,
                               'name': name, 'email': email})

            return HttpResponseRedirect(reverse('feedback_sent_page'))
    else:
        data = {'name': name, 'email': email}
        form = FeedbackForm(initial=data)

    return render_response(request, 'ui/feedback.html',
                           {'form': form,
                           'page_title': PTITLE % 'Feedback'})

def feedback_sent_view(request):
    return render_response(request, 'ui/feedback_sent.html', {})

@facebook.require_login()
def fb_login(request):
    user = authenticate(request=request)

    if user and user.is_active:
        login(request, user)

    if not user.email:
        next = '/email/'
    else:
        next = request.GET.get('next', reverse('home_page'))

    return HttpResponseRedirect(next)

@custom_login_required
def invite_view(request):
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            next = request.POST.get('ref_path', '')
            emails = form.cleaned_data['emails']
            message = form.cleaned_data['message']

            recipients = re.findall('[A-Za-z0-9\._@]+', emails)
            subject = 'Invitation from %s.' % request.user.get_profile().title
            t = template.loader.get_template('ui/invite_message.html')
            c = Context({'user': request.user, 'message': message})
            body = t.render(c)

            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)

            return HttpResponseRedirect(next or reverse('home_page'))
    else:
        form = InviteForm()
        next = request.GET.get('ref_path', '')

    return render_response(request, 'ui/invite.html',
                           {'form': form,
                           'next': next,
                           'page_title': PTITLE % 'Invite Friends'})

def uppers_view(request, target_type, target, page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    uppers = target.ratings.filter(rating=1).order_by('-date_added')
    uppers = make_paginator(uppers, page_no, num)
    paging_url = '/up/%s/%s/<PAGENO>/' % (target.ctype.id, target.id)

    page_title = PTITLE % ('Users who liked %s' % target.title)
    title = 'Users who liked '

    if isinstance(target, User):
        target = target.get_profile

    can_rate_or_flag = isinstance(target, RateFlag)
    can_follow = isinstance(target, Followable)

    return render_response(request, 'ui/ausers.html',
                           {'target': target, 'users': uppers,
                           'page_title': page_title,
                           'title': title,
                           'can_rate_or_flag': can_rate_or_flag,
                           'can_follow': can_follow,
                           'paging_url': paging_url})

def downers_view(request, target_type, target, page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    downers = target.ratings.filter(rating=-1).order_by('-date_added')
    downers = make_paginator(downers, page_no, num)
    paging_url = '/down/%s/%s/<PAGENO>/' % (target.ctype.id, target.id)

    page_title = PTITLE % ('Users who disliked %s' % target.title)
    title = 'Users who disliked '
    if isinstance(target, User):
        target = target.get_profile

    if isinstance(target, Node) or isinstance(target, Book):
        isprimarymodel = True
    else:
        isprimarymodel = False

    return render_response(request, 'ui/ausers.html',
                           {'target': target, 'users': downers,
                           'page_title': page_title,
                           'title': title,
                           'isprimarymodel': isprimarymodel,
                           'paging_url': paging_url})

def followers_view(request, target_type, target, page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    followers = target.followers.order_by('-date_added')
    followers = make_paginator(followers, page_no, num)
    paging_url = '/followers/%s/%s/<PAGENO>/' % (target.ctype.id, target.id)

    page_title = PTITLE % ('Followers of %s' % target.title)
    title = 'Followers of '
    if isinstance(target, User):
        target = target.get_profile

    if isinstance(target, Node) or isinstance(target, Book):
        isprimarymodel = True
    else:
        isprimarymodel = False

    return render_response(request, 'ui/ausers.html',
                           {'target': target, 'users': followers,
                           'page_title': page_title,
                           'title': title,
                           'isprimarymodel': isprimarymodel,
                           'paging_url': paging_url})

def users_view(request, page_no=1, num=ITEMS_PER_PAGE):

    term = request.GET.get('q', None)

    if term:
        term = term.lower()

        users = User.objects.filter(Q(username__icontains=term) |\
                                    Q(first_name__icontains=term) |\
                                    Q(last_name__icontains=term))

        MAX_USERS = 10
        users = [dict(id=u.id, name=u.get_profile().title)\
                    for u in users[:MAX_USERS]]
        if 'callback' in request.GET:
            response = '%s(%s)' % (request.GET['callback'], json.dumps(users))
        else:
            response = json.dumps(users)

        return HttpResponse(response, mimetype='application/json')

    if not request.user.is_superuser:
        error = "You don't have permission to see this page"
        return render_response(request, 'ui/users.html',
                           {'error':error})

    users = User.objects.order_by('-date_joined')
    users = make_paginator(users, page_no, num)
    paging_url = '/users/<PAGENO>/'

    page_title = PTITLE % ('Users')
    title = 'Users of Notemonk'

    return render_response(request, 'ui/users.html',
                           {'users': users,
                           'page_title': page_title,
                           'title': title,
                           'paging_url': paging_url})

def redeemables_view(request, page_no=1, num=ITEMS_PER_PAGE):
    redeemables = RedeemableItem.objects.exclude(num=0).order_by('-credits')
    redeemables = make_paginator(redeemables, page_no, num)
    paging_url = '/redeemables/<PAGENO>'
    return render_response(request, 'ui/redeemables.html',
            {'redeemables': redeemables,
            'page_title': PTITLE % 'Redeemables',
            'paging_url': paging_url})

def redeemable_view(request, item_id):
    redeemable = RedeemableItem.objects.get(id=int(item_id))
    page_title = PTITLE % ('Redeemable - %s' % xcode(redeemable.title),)
    return render_response(request, 'ui/redeemable.html',
            {'redeemable': redeemable,
            'page_title': page_title})

def redemption_view(request, r_id):

    show_msg = request.GET.get('msg', None)
    redemption = Redemption.objects.get(id=r_id)
    redemption_items = RedemptionItem.objects.filter(redemption=redemption)
    more_info = False

    user = request.user
    if user.is_superuser or user.is_staff or redemption.user == user:
        more_info = True

    message = ''
    if show_msg:
        message = 'Checkout done. You will receive the items within 15 days from the end of this month'

    return render_response(request, 'ui/redemption.html',
            {'redemption': redemption,
            'redemption_items': redemption_items,
            'more_info': more_info,
            'error': message})

@custom_login_required
def cart_add_view(request, item_id, num_items):
    redeemable = RedeemableItem.objects.get(id=item_id)

    if redeemable.num:
        num_items = int(num_items) if num_items else 0
        cart = request.session.get('cart', [])

        if item_id not in dict(cart):
            cart.append([item_id, num_items or 1])

        else:
            for index, (cur_item_id, num) in enumerate(cart):
                if cur_item_id == item_id:
                    cart[index] = [item_id, num_items or (num + 1)]
                    break

        request.session['cart'] = cart

    next = request.GET.get('next', reverse('home_page'))
    return HttpResponseRedirect(next)

@custom_login_required
def cart_remove_view(request, item_id):
    cart = request.session.get('cart', [])

    for index, (cur_item_id, num) in enumerate(cart):
        if cur_item_id == item_id:
            cart[index] = None

    request.session['cart'] = [x for x in cart if x is not None]

    next = request.GET.get('next', reverse('home_page'))
    return HttpResponseRedirect(next)

@custom_login_required
def cart_checkout_view(request):

    profile = request.user.get_profile()

    if request.method == 'POST':
        form = MailingAddressForm(request.POST)
        if form.is_valid():
            mailing_address = form.cleaned_data['mailing_address']
            profile.mailing_address = mailing_address
            profile.save()

            r = Redemption.add(request.session['cart'], request.user)
            del request.session['cart']

            if r:
                followers = get_followers(profile)
                Activity.add(request.user, r)
                notification.send(followers, 'user_redeemed',
                            {'user': request.user, 'redemption': r})
            else:
                request.session['cart'] = []
                return render_response(request, 'ui/base.html',
                    {'error': 'Someone grabbed the items before you did. Try again.'})

            return HttpResponseRedirect(reverse('redemption_page',
                                        kwargs={'r_id': r.id}) + '?msg=1')
    else:
        form = MailingAddressForm(initial =
                    {'mailing_address': profile.mailing_address})

    return render_response(request, 'ui/cart_checkout.html',
                           {'form': form,
                           'page_title': PTITLE % 'Checkout'})

@ensure_no_mem_file
@custom_login_required
def insert_image_view(request, target_type=None, target=None):

    if target_type is not None and target is not None:
        target = get_target(target_type, target)

    url = ''
    error = ''
    title = ''
    alt = ''

    if request.method == 'POST':
        url = request.POST.get('url', '')
        title = request.POST.get('title', '')
        alt = request.POST.get('alt', '')

        image = request.FILES.get('image')

        if image:
            path = image.temporary_file_path()
            try:
                PIL.open(path)
            except IOError:
                error = 'Please upload only image files'

        if image and not error:

            title = title or image.name
            alt = alt or image.name

            data = image.read()
            checksum = hashlib.md5(data).hexdigest()

            try:
                ufile = UploadedFile.objects.get(checksum=checksum)
            except ObjectDoesNotExist:
                ufile = UploadedFile.objects.create(checksum=checksum,
                    uploader=request.user)
                cfile = ContentFile(data)
                ufile.file.save(image.name, cfile, save=True)
                ufile.save()

            url = ufile.file.url

            if target:
                try:
                    attachment = target.attachments.get(uploaded_file=ufile)
                    title = title or attachment.title
                except ObjectDoesNotExist:
                    attachment = target.attach(request.user, ufile=ufile, title=title)

    return render_response(request, 'ui/insert_image.html',
                           {'error': error, 'alt': alt,
                           'url': url, 'title': title})

def attachments_view(request, target_type, target, page_no=1, num=ITEMS_PER_PAGE):
    target = get_target(target_type, target)
    attachments = make_paginator(target.attachments.all(), page_no, num)
    page_title = PTITLE % ('Attachments for %s' % target.title)
    paging_url = '/attachments/%d/%d/<PAGENO>/' % (target.ctype.id, target.id)
    return render_response(request, 'ui/attachments.html',
        {'target': target, 'attachments': attachments,
         'page_title': page_title, 'paging_url': paging_url})

def attachment_view(request, attachment_id):
    attachment = Attachment.objects.get(id=attachment_id)
    page_title = PTITLE % ('Attachment: %s' % attachment.title)

    is_editable = False
    if not request.user.is_anonymous():
        is_editable = attachment.is_editable_by(request.user)

    return render_response(request, 'ui/attachment.html',
        {'attachment': attachment, 'page_title': page_title,
         'is_editable': is_editable})

@custom_login_required
def attachment_add_view(request, target_type, target):
    target = get_target(target_type, target)
    url = ''
    error = ''

    if request.method == 'POST':

        url = request.POST.get('url', '')

        f = request.FILES.get('file')
        if f:

            checksum = get_md5(f)
            f.seek(0)
            print 'checksum is ', checksum
            try:
                print 'insdie try'
                ufile = UploadedFile.objects.get(checksum=checksum)
                print 'ufile is ', ufile
            except ObjectDoesNotExist:
                ufile = UploadedFile.objects.create(checksum=checksum,
                    uploader=request.user)
                ufile.file.save(f.name, f, save=True)
                ufile.save()

            url = ufile.file.url

            try:
                attachment = target.attachments.get(uploaded_file=ufile)
            except ObjectDoesNotExist:
                attachment = target.attach(request.user, ufile=ufile, title='attachment')
                attachment.rate_up(request.user)
                attachment.save()
                ac = Activity.add(request.user, attachment)
                add_to_book_stream(attachment, ac)

        elif url:

            try:
                attachment = target.attachments.get(url=url)
            except ObjectDoesNotExist:
                attachment = target.attach(request.user, url=url, title='attachment')
                attachment.rate_up(request.user)
                attachment.save()

        return HttpResponseRedirect(reverse('attachment_edit_page',
                            kwargs={'attachment_id': attachment.id}))

    return render_response(request, 'ui/attachment_add.html',
                           {'error': error, 'url': url, 'target': target})

@custom_login_required
def attachment_edit_view(request, attachment_id):
    error = False
    attachment = Attachment.objects.get(id=attachment_id)
    page_title = PTITLE % ('Attachment: %s' % attachment.title)

    #FIXME: check if attachment is editable by current user

    if request.method == 'POST':
        title = request.POST.get('title', 'attachment')
        description = request.POST.get('description', '')
        url = request.POST.get('url', '')

        if not attachment.uploaded_file and not url:
            error = True

        if not title.strip():
            error = True

        if not error:
            attachment.title = title
            attachment.description.raw = description
            if url:
                attachment.url = url
            attachment.save()

        return HttpResponseRedirect(reverse('attachment_page',
                            kwargs={'attachment_id': attachment.id}))

    else:
        return render_response(request, 'ui/attachment_edit.html',
            {'attachment': attachment, 'page_title': page_title})

@custom_login_required
def comment_add_view(request, target_type, target):
    next = request.GET.get('next', '')

    if request.method == 'POST':
        text = request.POST.get('text', '').strip()

        if text:
            target = get_target(target_type, target)
            comment = target.add_comment(user=request.user, text=text)

            followers = get_followers(request.user.get_profile(), target)
            notification.send(followers, 'comment_add', {'comment': comment})

            ac = Activity.add(request.user, comment)

            if request.user != target.user:
                target.user.get_profile().stream.add(ac)

            if isinstance(target, ProfilePost) and request.user != target.profile.user:
                target.profile.stream.add(ac)

            add_to_book_stream(target, ac)

    return HttpResponseRedirect(next)

@custom_login_required
def comment_edit_view(request, comment_id):
    pass

def profilepost_view(request, profilepost_id):
    profilepost = ProfilePost.objects.get(id=profilepost_id)
    page_user = profilepost.user

    title = "%s's %s" % (profilepost.user.get_profile().title, 'ProfilePost')
    page_title = PTITLE % title

    return render_response(request, 'ui/profilepost.html',
            {'profilepost': profilepost, 'page_title': page_title,
            'page_user': page_user,})

@custom_login_required
def profilepost_add_view(request, profile_id):
    next = request.GET.get('next', '')
    profile = UserProfile.objects.get(id=profile_id)

    if request.method == 'POST':
        text = request.POST.get('text', '').strip()

        if text:
            post = ProfilePost.objects.create(user=request.user, text=text,
                profile=profile)
            post.rate_up(request.user)
            post.save()

            followers = get_followers(profile, request.user.get_profile())
            notification.send(followers, 'ppost_add', {'post': post})

            ac = Activity.add(request.user, post)

            if profile.user != request.user:
                profile.stream.add(ac)

    return HttpResponseRedirect(next)

@custom_login_required
def profilepost_edit_view(request, post_id):
    pass

ALLITEMS_MAP = {'questions': Question, 'notes': Note, 'videos': AssociatedMedia}
def allitems_view(request, u_items=None, order='recent', page_no=1, num=ITEMS_PER_PAGE):

    if u_items not in ALLITEMS_MAP:
        return render_error(request, 'Unable to display items')

    klass = ALLITEMS_MAP[u_items]
    qorder = '-date_added' if order == 'recent' else '-score'
    items = klass.objects.all().order_by(qorder)
    items = make_paginator(items, page_no, num)

    title = '%s %s' % (order.capitalize(), u_items.capitalize())
    page_title = PTITLE % title
    paging_url = '/%s/all/%s/<PAGENO>/' % (u_items, order)
    return render_response(request, 'ui/allitems.html',
        {'page_title': page_title, 'items': items,
         'paging_url': paging_url, 'title': title,
         'u_items': u_items, 'order': order})

def handler_500(request):
    t = template.loader.get_template('ui/500.html')
    context = RequestContext(request, {})
    context['ref_path'] = '/'
    return HttpResponseServerError(t.render(context))

def handler_404(request):
    return render_response(request, 'ui/404.html')

def xd_receiver_view(request):
    return render_response(request, 'xd_receiver.htm')

