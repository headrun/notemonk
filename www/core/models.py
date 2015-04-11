from decimal import Decimal
from itertools import groupby

import simplejson as json
import Image

from django.db import models, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django import template

import reversion
import notification.models as notification
from markitup.fields import MarkupField

from core.utils import xcode, urlsafe, get_target, HANDLING_CREDITS
from core.utils import make_context, QuerySetFilter, parse_flags

Q = models.Q
LIMIT = 50

def user_post_save_handler(**kwargs):
  
    obj = kwargs['instance']
  
    if not isinstance(obj, User):
        return
  
    if 'created' not in kwargs:
        return
  
    if not kwargs['created']:
        return
  
    try:
        profile = UserProfile.objects.get(user=obj)
    except ObjectDoesNotExist:
        profile = UserProfile.objects.create(user=obj)
        stream = Stream.objects.create(title='for user: %s' % obj.username)
        profile.stream = stream
        profile.save()

        Note.add(profile, user=obj)

        followers = User.objects.filter(is_superuser=True)
        notification.send(followers, '_user_joined', {'user': obj})

post_save.connect(user_post_save_handler)

def get_book(object):
    target = object

    while target:
       if isinstance(target, Book):
           return target
       
       target = getattr(target, 'target', None)

class Titled(models.Model):
    title = models.CharField(max_length=255)
    
    class Meta:
        abstract = True

class Editable(models.Model):
    def is_editable_by(self, user):
        return user.is_superuser or user.is_staff or user == self.user

    @property
    def edit_link(self):
        return ''
    
    class Meta:
        abstract = True

class Referred(models.Model):
    @property
    def ctype(self):
        return ContentType.objects.get_for_model(self)

    class Meta:
        abstract = True

class Followable(models.Model):
    followcount = models.IntegerField(db_index=True, default=0)

    followers = generic.GenericRelation('Follows',
                        content_type_field='target_type',
                        object_id_field='target_id')

    class Meta:
        abstract = True

    def follow(self, user):
        try:
            f = self.followers.create(user=user)
            self.followcount += 1
            self.save()
            return f
        except IntegrityError:
            # Model has already been followed by this user
            # No more action is required. Ignore.
            pass

    def unfollow(self, user):
        try:
            obj = self.followers.get(user=user).delete()
            self.followcount -= 1
            self.save()
        except IntegrityError:
            # Model has already been followed by this user
            # No more action is required. Ignore.
            pass

    def unfollow(self, user):
        try:
            obj = self.followers.get(user=user).delete()
            self.followcount -= 1
            self.save()
        except ObjectDoesNotExist:
            # Model has not been followed by this user
            # No more action is required. Ignore.
            pass

    def followed_by(self, user):
        return True if self.followers.filter(user=user) else False

    @property
    def followers_link(self):
        return '/followers/%d/%d/' % (self.ctype.id, self.id)

class Rateable(models.Model):
    LEVELS = [2, 10, 50, 100, 1000, 10000, 100000, 1000000,
              10000000, 100000000, 1000000000]

    tot_count = models.IntegerField(db_index=True, default=0)
    up_count = models.IntegerField(db_index=True, default=0)
    down_count = models.IntegerField(db_index=True, default=0)
    score = models.IntegerField(db_index=True, default=0)

    ratings = generic.GenericRelation('Ratings',
                        content_type_field='target_type',
                        object_id_field='target_id')

    class Meta:
        abstract = True

    def notify_rating(self):
        if self.tot_count not in self.LEVELS:
            return

        RatingNotification.objects.create(target_type=self.ctype, target_id=self.id,
                                          num_ratings=self.tot_count)

    def rate_up(self, user):
        try:
            r = self.ratings.create(user=user, rating=Ratings.UP)
            self.tot_count += 1
            self.up_count += 1
            self.score += 1
            self.notify_rating()
            return r
        except IntegrityError:
            # Model has already been rated by this user
            pass

    def rate_down(self, user):
        try:
            r = self.ratings.create(user=user, rating=Ratings.DOWN)
            self.tot_count += 1
            self.down_count += 1
            self.score -= 1
            self.notify_rating()
            return r
        except IntegrityError:
            # Model has already been rated by this user
            pass

    @property
    def level(self):
        tot_count = self.tot_count

        for index, level_start in enumerate(self.LEVELS):
            if tot_count < level_start:
                return index + 1

        return len(self.LEVELS) + 1

class Flaggable(models.Model):
    flagcount = models.IntegerField(db_index=True, default=0)

    flaggers = generic.GenericRelation('Flags',
                        content_type_field='target_type',
                        object_id_field='target_id')

    class Meta:
        abstract = True

    def flag(self, user):
        try:
            f = self.flaggers.create(user=user)
            self.flagcount += 1
            return f
        except IntegrityError:
            # Model has already been flagged by this user
            # No more action is required. Ignore.
            pass

    def unflag(self, user):
        try:
            obj = self.flaggers.get(user=user).delete()
            self.flagcount -= 1
        except ObjectDoesNotExist:
            # Model has not been flagged by this user
            # No more action is required. Ignore.
            pass

class HasComments(models.Model):
    commentcount = models.IntegerField(db_index=True, default=0)

    comments = generic.GenericRelation('Comment',
                        content_type_field='target_type',
                        object_id_field='target_id')

    class Meta:
        abstract = True

    def add_comment(self, user, text):
        comment = self.comments.create(user=user, text=text)
        self.commentcount += 1
        self.save()
        return comment

class RateFlag(Rateable, Flaggable):
    class Meta:
        abstract = True

class Linkable(models.Model):
    @property
    def link(self):
        pass

    class Meta:
        abstract = True

class Tagable(models.Model):
    tags = generic.GenericRelation('TagItem',
                content_type_field='item_type',
                object_id_field='item_id')

    class Meta:
        abstract = True

class Renderable:
    TEMPLATE = ''
    RENDER_ARGS = []
    DEFAULT_FLAGS = 'text,addedby,rate,flag,follow,dateadded,context'
    MODEL_DEFAULT_FLAGS = ''

    def render(self, context, *args):
        t = template.loader.get_template(self.TEMPLATE)

        args = list(args)
        request = context['request']

        flags = {}

        dflags = parse_flags(self.DEFAULT_FLAGS)
        mdflags = parse_flags(self.MODEL_DEFAULT_FLAGS)
        cur_flags = parse_flags(args.pop(0) if args else '')
        
        flags.update(dflags)
        flags.update(mdflags)
        flags.update(cur_flags)

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if 'MSIE' in user_agent:
            # Disable overlay in IE6 as it causes crash!
            flags['is_overlay'] = False
        
        R = self.RENDER_ARGS
        kwargs = {}
        if args and self.RENDER_ARGS:
            kwargs = dict([(R[i], args[0]) for i in xrange(len(args))])

        c = make_context(context)
        c['obj'] = self
        c['args'] = args
        c['kwargs'] = kwargs
        c['flags'] = flags
        c['request'] = request
        c['ref_path'] = context['ref_path'] if 'ref_path' in context else '/'
        c['user'] = request.user
        
        return t.render(c)

class GroupRenderer:
    GROUP_TEMPLATE = ''

    @classmethod
    def render_group(self, items):
        pass

class ItemGroup(Renderable):

    def __init__(self, items):
        self.items = items

    def render(self, context, *args):
        # pick last item as group handler
        # not picking first item as it might
        # be a different type
        item = self.items[-1]

        klass = item.target.__class__
        return klass.render_group(context, self.items)

class HasAttachments(models.Model):

    attachments = generic.GenericRelation('Attachment',
                        content_type_field='target_type',
                        object_id_field='target_id')

    @property
    def attachments_link(self):
        return '/attachments/%d/%d/' % (self.ctype.id, self.id)

    def can_attach(self, user):
        if user.is_superuser or user.is_staff:
            return True

        if user == getattr(self, 'user', None):
            return True

        if hasattr(self, 'moderators'):
            if user in self.moderators.all():
                return True

    def attach(self, user,
               title='', description='',
               url=None, ufile=None):

        assert(url or ufile)

        a = Attachment.objects.create(attacher=user, title=title,
                                description=description,
                                target_id=self.id,
                                target_type=self.ctype,
                                url=url,
                                uploaded_file=ufile)
        return a

    class Meta:
        abstract = True

class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/%Y/%m/%d')
    checksum = models.CharField(max_length=32, unique=True)
    date_added = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField()
    uploader = models.ForeignKey(User)
    
    @property
    def user(self):
        return self.uploader

class Attachment(Referred, RateFlag, Linkable, Renderable, Editable):
    TEMPLATE = 'renderables/attachment.html'

    title = models.CharField(max_length=255, blank=True, null=True)
    description = MarkupField(null=True, blank=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    url = models.TextField(max_length=2048, null=True, blank=True)
    uploaded_file = models.ForeignKey(UploadedFile, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    attacher = models.ForeignKey(User)

    questions = generic.GenericRelation('Question',
                            content_type_field='target_type',
                            object_id_field='target_id')

    def is_target_book(self):
        return bool(get_book(self))

    def is_editable_by(self, user):
        book = get_book(self)
        book_editable = False
        if book:
            book_editable = book.is_editable_by(user)
        return Editable.is_editable_by(self, user) or book_editable
    
    @property
    def edit_link(self):
        return '/attachment/edit/%d/' % self.id

    @property
    def user(self):
        return self.attacher

    @property
    def link(self):
        return '/attachment/%s/%s/' % (self.id, urlsafe(self.title)[:LIMIT])

    @property
    def verb(self):
        return 'attached'

    class Meta:
        unique_together = ('target_type', 'target_id', 'uploaded_file')

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    description = MarkupField(null=True, blank=True)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

class TagItem(models.Model):
    tag = models.ForeignKey(Tag)

    item_type = models.ForeignKey(ContentType)
    item_id = models.PositiveIntegerField(db_index=True)
    item = generic.GenericForeignKey('item_type', 'item_id')

    class Meta:
        unique_together = (('tag', 'item_type', 'item_id'),)

    def __unicode__(self):
        return u'%s [%s]' % (self.item, self.tag)

class Category(Tagable):
    QUERY_TYPES = (('any', 'Any'), ('all', 'All'))
    name = models.CharField(max_length=100, db_index=True)
    description = MarkupField(null=True, blank=True)
    parent = models.ForeignKey('self', null=True)
    query_type = models.CharField(max_length=8, null=False, blank=False,
                    choices=QUERY_TYPES)

class LeaderBoardData(models.Model):

    tag = models.CharField(max_length=32, db_index=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    def __unicode__(self):
        return '<LeaderBoardData %s: %s>' % (self.tag, self.target)

class RatingNotification(models.Model):
    time = models.DateTimeField(auto_now_add=True, db_index=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    num_ratings = models.IntegerField()

    def __unicode__(self):
        return '<RatingNotification %s: %s>' % (self.target, self.num_ratings)


class Comment(Referred, Flaggable, Renderable, Editable):
    TEMPLATE = 'renderables/comment.html'
    GROUP_TEMPLATE = 'renderables/comment_group.html'

    user = models.ForeignKey(User)
    text = models.TextField(max_length=1024)
    date_added = models.DateTimeField(auto_now_add=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    @classmethod
    def render_group(self, context, items):

        target = items[-1].target.target
        t = template.loader.get_template(self.GROUP_TEMPLATE)
        c = make_context(context)
        c['comments'] = items
        c['target'] = target
        return t.render(c)

    def is_editable_by(self, user):
        return Editable.is_editable_by(self, user)
    
    @property
    def edit_link(self):
        return '/comment/edit/%d/' % self.id

    @property
    def title(self):
        return 'Comment: %s' % xcode(self.text[:LIMIT])

    @property
    def link(self):
        return self.target.link

class Activity(models.Model, Renderable):
    TEMPLATE = 'renderables/activity.html'

    ACTION_TYPES = (('added', 'Added'), ('modified', 'Modified'))

    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)
    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')
    action = models.CharField(max_length=8, null=False, blank=False,
                    default='added', choices=ACTION_TYPES)
    data = models.TextField(max_length=1024, null=True, blank=True)

    @classmethod
    def add(self, user, target, action='added', data=None):
        if target is None:
            raise Exception('activity target cannot be None')
        
        a = self.objects.create(user=user, data=repr(data),
                                target_type = target.ctype,
                                target_id = target.id,
                                action=action)
        return a

    class Meta:
        ordering = ('-id',)

class Stream(Titled):

    def add(self, activity):
        try:
            sitem = StreamItem.objects.create(stream=self, activity=activity)
        except IntegerField:
            sitem = StreamItem.objects.get(stream=self, activity=activity)

        return sitem

    def __unicode__(self):
        return 'Stream: %d: %s' % (self.id, self.title)

class StreamItem(models.Model):

    date_added = models.DateTimeField(auto_now_add=True)
    stream = models.ForeignKey(Stream)
    activity = models.ForeignKey(Activity)

    class Meta:
        unique_together = ('stream', 'activity')

    def __unicode__(self):
        return 'StreamItem: %d of %s: %s' % (self.id, self.stream, self.activity)

class Question(Referred, RateFlag, HasComments, Linkable, HasAttachments, Renderable, Editable):
    TEMPLATE = 'renderables/question.html'
    MODEL_DEFAULT_FLAGS = 'answercount,topanswer'

    user = models.ForeignKey(User)
    text = MarkupField()
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now_add=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    def is_editable_by(self, user):
        book = get_book(self)
        book_editable = False
        if book:
            book_editable = book.is_editable_by(user)
        return Editable.is_editable_by(self, user) or book_editable

    @property
    def title(self):
        return 'Question: %s under %s' % (self.text.raw[:LIMIT], self.target.title)

    @property
    def top_answer(self):
        # FIXME
        if self.answer_set.all():
            ans = Answer.objects.filter(question=self)[0]
            return ans
        else:
            return None

    @classmethod
    def add(self, user, target, text):
        q = self.objects.create(user=user, text=text,
                                target_type = target.ctype,
                                target_id = target.id)
        return q

    class Meta:
        ordering = ('-score',)

    @property
    def link(self):
        return '/qa/question/%s/%s/' % (self.id, urlsafe(self.text.raw[:LIMIT]))
    
    def __unicode__(self):
        return self.text.raw

class Answer(Referred, RateFlag, HasComments, Linkable, HasAttachments, Renderable, Editable):
    TEMPLATE = 'renderables/answer.html'

    user = models.ForeignKey(User)
    question = models.ForeignKey(Question)
    text = MarkupField()

    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now_add=True)

    def is_editable_by(self, user):
        book = get_book(self)
        book_editable = False
        if book:
            book_editable = book.is_editable_by(user)
        return Editable.is_editable_by(self, user) or book_editable

    @property
    def title(self):
        return 'Answer: %s under %s' % (xcode(self.text.raw[:LIMIT]),
                                        xcode(self.question.text.raw[:LIMIT]))

    @property
    def target(self):
        return self.question

    class Meta:
        ordering = ('-score',)

    @property
    def link(self):
        return self.question.link
    
    def __unicode__(self):
        return self.text.raw

class FBUserProfile(models.Model):
    user = models.ForeignKey(User, unique=True)
    uid = models.CharField(max_length=100)

class UserProfile(Referred, RateFlag, Followable, Linkable, Renderable, Editable):

    # means: level 1: 0 to 9, level 2: 10 to 19 and so on.
    LEVELS = (10, 20, 40, 60, 80, 120, 160, 200, 240, 300, 360, 420, 500, 600,
              700, 800, 1000, 1250, 1500, 2000)

    LEVEL_NAMES = (
        'Wild Monkey',
        'Chattering Monkey',
        'Cheeky Monkey',
        'Curious Monkey',
        'Active Monkey',
        'Power Monkey',
        'Brainy Monkey',
        'Genius Monkey',
        'Learned Monkey',
        'Master Monkey',
        'Vedic Monkey',
        'Guru Monkey',
        'Shining Monkey',
        'Monkey King',
        'Monk Monkey',
        'Monkey Monk',
        'Budding Monk',
        'Trainee Monk',
        'Monk-to-be',
        'Monk'
    )
    
    TEMPLATE = 'renderables/userprofile.html'

    user = models.ForeignKey(User, unique=True)
    stream = models.ForeignKey(Stream, unique=True, null=True)
    institution = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=200, null=True, blank=True)
    state = models.CharField(max_length=200, null=True, blank=True)
    country = models.CharField(max_length=200, null=True, blank=True)
    dob = models.DateTimeField(null=True, blank=True)
    sex = models.CharField(max_length=1, null=True, blank=True)
    image = models.ImageField(upload_to='images/user/%Y/%m/%d')
    points = models.IntegerField(db_index=True, default=0)
    credits = models.DecimalField(max_digits=10, decimal_places=2,
                null=False, default=Decimal(str(0.0)))
    mailing_address = models.TextField(null=True, blank=True)
    referrer = models.ForeignKey(User, null=True, db_index=True,
                                 related_name='referee')
    
    def is_editable_by(self, user):
        return Editable.is_editable_by(self, user)

    @property
    def books(self):
        return Book.objects.filter(Q(user=self.user) | Q(moderators__id=self.user.id))

    @property
    def following_books(self):
        target_type = ContentType.objects.get_for_model(Book)
        following = Follows.objects.filter(user=self.user,
                                           target_type=target_type)
        following = QuerySetFilter(following, lambda x: x.target)
        return following

    @property
    def referred(self):
        return UserProfile.objects.filter(referrer=self)

    @property
    def level(self):
        points = self.points

        for index, level_start in enumerate(self.LEVELS):
            if points < level_start:
                return index + 1

        return len(self.LEVELS)

    @property
    def level_name(self):
        return self.LEVEL_NAMES[self.level - 1]

    @property
    def points_for_current_level(self):
        return self.LEVELS[self.level - 1]

    def give_points(self, points):
        level = self.level
        self.points += points
        new_level = self.level

        if level == new_level:
            return

        # notify user and his followers about level change
        followers = [self.user]
        followers.extend([f.user for f in self.followers.all()])
        followers = list(set(followers))

        notification.send(followers, 'user_level_changed',
                            {'user': self.user})

        # award points to referrer
        from core.points import give_points
        give_points('user_level_changed', user=self.user.id,
                        prev_level=level, level=new_level)

    @property
    def points_history(self):
        return PointsHistory.objects.filter(user=self.user)

    @property
    def location(self):
        location = [self.city, self.state, self.country]
        location = [loc or '' for loc in location if loc]
        location = ', '.join(location)
        return location

    @property
    def title(self):
        return self.user.get_full_name().strip() or self.user.username

    @property
    def note(self):
        return Note.objects.get(target_id=self.id,
                                target_type=self.ctype.id)
    
    @property
    def videos(self):
        video_type = ContentType.objects.get_for_model(Video)
        media = AssociatedMedia.objects.filter(user=self.user,
                                               media_type=video_type)
        return media
    
    @property
    def questions(self):
        return Question.objects.filter(user=self.user)
    
    @property
    def answers(self):
        return Answer.objects.filter(user=self.user)
    
    @property
    def notes(self):
        return Note.objects.filter(user=self.user)

    @property
    def comments(self):
        return Comment.objects.filter(user=self.user)
    
    @property
    def following(self):
        target_type = ContentType.objects.get_for_model(UserProfile)
        following = Follows.objects.filter(user=self.user,
                                           target_type=target_type)
        following = QuerySetFilter(following, lambda x: x.target)
        return following
    
    @property
    def activities(self):
        return Activity.objects.filter(user=self.user)

    @property
    def link(self):
        return '/user/%s/' % urlsafe(self.user.username)

    @property
    def can_add_book(self):
        return True

    def can_edit_book(self, book):
        return book.is_editable_by(self.user)

    @property
    def followers_link(self):
        return '/user/%s/followers/' % urlsafe(self.user.username)

    @property
    def following_books_link(self):
        return '/user/%s/fbooks/' % urlsafe(self.user.username)

    @property
    def following_link(self):
        return '/user/%s/following/' % urlsafe(self.user.username)


class Toppers(models.Model):
    user_profile = models.ForeignKey(UserProfile)

class Onliners(models.Model):
    user = models.ForeignKey(User)

class ProfilePost(Referred, RateFlag, HasComments, Renderable, Editable, Linkable):
    TEMPLATE = 'renderables/profilepost.html'
    MODEL_DEFAULT_FLAGS = 'comment'

    user = models.ForeignKey(User)
    profile = models.ForeignKey(UserProfile)
    text = models.TextField(max_length=1024)
    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def edit_link(self):
        return '/profilepost/edit/%d/' % self.id

    @property
    def link(self):
        return '/profilepost/%d/' % self.id
    
    @property
    def target(self):
        return self.profile

    @property
    def type(self):
        return 'status'

    @property
    def title(self):
        return 'ProfilePost: %s' % (xcode(self.text[:LIMIT]))

class RedeemableItem(Titled, Renderable):
    TEMPLATE = 'renderables/redeemableitem.html'

    description = MarkupField(null=True, blank=True)
    credits = models.DecimalField(max_digits=10, decimal_places=2,
                null=False, default=Decimal(str(0.0)))
    date_added = models.DateTimeField(auto_now_add=True, db_index=True)
    image = models.ImageField(upload_to='images/%Y/%m/%d')
    num = models.IntegerField(null=False, default=1, db_index=True)

    @property
    def link(self):
        return '/redeemable/%d/%s/' % (self.id, urlsafe(self.title[:LIMIT]))

    def __unicode__(self):
        return self.title

class Redemption(Referred, Renderable):
    TEMPLATE = 'renderables/redemption.html'

    date_added = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User)
    items = models.ManyToManyField(RedeemableItem, through='RedemptionItem')
    credits = models.DecimalField(max_digits=10, decimal_places=2,
                null=False, default=Decimal(str(0.0)))
    date_processed = models.DateTimeField(null=True)
    
    @property
    def link(self):
        return '/redemption/%d/' % self.id

    @property
    def verb(self):
        return 'redeemed'

    @property
    def title(self):
        return 'Redemption by %s (order no: %d)' % \
            (self.user.get_profile().title, self.id)

    def __unicode__(self):
        return 'order %d for user %s for %s credits' % (self.id,
            self.user, self.credits)

    @classmethod
    def add(self, cart_data, user):
        cart = []
        total_credits = Decimal('0.0')

        for item_id, num in cart_data:
            item = RedeemableItem.objects.get(id=int(item_id))

            if item.num < num:
                return

            total_credits += (item.credits * num)
            cart.append([item, num])

        total_credits += HANDLING_CREDITS

        profile = user.get_profile()
        if profile.credits < total_credits:
            return

        redemption = self.objects.create(user=user, credits=total_credits)

        for item, num in cart:
            r = RedemptionItem.objects.create(redemption=redemption, item=item, num=num)
            item.num -= num
            item.save()
       
        profile.credits -= total_credits
        profile.save()

        return redemption

class RedemptionItem(models.Model, Renderable):
    TEMPLATE = 'renderables/redemptionitem.html'

    redemption = models.ForeignKey(Redemption)
    item = models.ForeignKey(RedeemableItem)
    num = models.IntegerField(null=False, default=1)
    
    def __unicode__(self):
        return '%s item %d nos for order %d' % (self.item.title,
            self.num, self.redemption.id)

class PointsHistory(Renderable, Referred):
    TEMPLATE = 'renderables/pointshistory.html'
    GROUP_TEMPLATE = 'renderables/pointshistory_group.html'

    user = models.ForeignKey(User, db_index=True)
    date_added = models.DateTimeField(auto_now_add=True, db_index=True)
    points = models.IntegerField()
    code = models.CharField(max_length=32)
    data = models.TextField(max_length=2000)

    @property
    def edata(self):
        edata = eval(self.data)

        if 'target_type' in edata and 'target' in edata:
            target = get_target(edata['target_type'], edata['target'])
            edata['target'] = target
            del edata['target_type']

        return edata

    @property
    def has_all_rated_data(self):
        edata = self.edata
        return self.code == 'rated' and 'position' in edata

    @property
    def target(self):
        if self.code == 'rated':
            return self.edata['target']

        elif self.code == 'user_level_changed':
            try:
                return User.objects.get(id=self.edata['user']).get_profile()
            except ObjectDoesNotExist:
                pass

    @property
    def is_for_adding(self):
        edata = self.edata

        if not self.code == 'rated':
            return False

        if not self.has_all_rated_data:
            return False

        if isinstance(edata['target'], UserProfile):
            return False

        return edata['position'] == 0

    @property
    def get_rating(self):
        if not self.code == 'rated':
            return None

        return self.edata['target'].ratings.get(user=self.user)

    @property
    def verb(self):
        verb = 'rated'
        edata = self.edata

        if self.code == 'rated':
            if self.is_for_adding:
                verb = 'adding'
            else:
                verb = 'liking' if self.get_rating.rating == Ratings.UP else 'disliking'

        elif self.code == 'user_level_changed':
            verb = 'referring'

        return verb

    @property
    def has_gained(self):
        return self.points > 0

    @property
    def signed_points(self):
        return '+%s' % self.points if self.has_gained else str(self.points)

    @property
    def sign(self):
        return '+' if self.has_gained else '-'

    @classmethod
    def render_group(self, context, items):

        activities = items[:]
       
        # group by user
        items.sort(key=lambda x: x.target.user.username)
        groups = groupby(items, lambda x: x.target.user)
        groups = [(k, list(citems)) for k, citems in groups]

        t = template.loader.get_template(self.GROUP_TEMPLATE)
        c = make_context(context)
        c['groups'] = groups
        c['activities'] = activities
        return t.render(c)

    @property
    def title(self):
        return '%s for %s %s' % (self.signed_points, self.verb, self.target.title)
        
    def __unicode__(self):
        return '<Points "%s:%d" for "%s">' % (self.code, self.points, self.user)

    class Meta:
        ordering = ('-date_added',)

class Note(Referred, RateFlag, Linkable, HasAttachments, Editable, Renderable):
    TEMPLATE = 'renderables/note.html'

    text = MarkupField()
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, null=True)
    
    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')
    
    questions = generic.GenericRelation(Question,
                            content_type_field='target_type',
                            object_id_field='target_id')

    def is_editable_by(self, user):
        book = get_book(self)
        book_editable = False
        if book:
            book_editable = book.is_editable_by(user)
        return Editable.is_editable_by(self, user) or book_editable

    @classmethod
    def add(self, target, text='', user=None):
        q = self.objects.create(text=text, user=user, flagcount=0,
                                target_type = target.ctype,
                                target_id = target.id)
        return q

    class Meta:
        unique_together = ('target_type', 'target_id', 'user')
        ordering = ('-score',)
   
    @property
    def title(self):
        return 'Note: %s' % self.target.title

    @property
    def link(self):
        return '/note/%s/' % self.id

if not reversion.is_registered(Note):
    reversion.register(Note, fields=['text', '_text_rendered'])

class Content(Referred, Linkable):
    date_added = models.DateTimeField(auto_now_add=True)
    _notes = generic.GenericRelation(Note, default='',
                            content_type_field='target_type',
                            object_id_field='target_id')
    questions = generic.GenericRelation(Question,
                            content_type_field='target_type',
                            object_id_field='target_id')

    def __unicode__(self):
        return self.title

    class Meta:
        abstract = True

    @property
    def notes(self):
        return self._notes.all()

    @property
    def note(self):
        notes = self._notes.all()[:1]
        return notes[0] if notes else None
    
    def user_note(self, user):
        if not user.is_authenticated():
            return

        try:
            return self._notes.get(user=user)
        except ObjectDoesNotExist:
            return

class PrimaryContent(Content, Titled, RateFlag, HasAttachments):

    class Meta:
        abstract = True

    @property
    def images(self):
        target_type = ContentType.objects.get_for_model(self)
        image_type = ContentType.objects.get_for_model(Image)

        media = AssociatedMedia.objects.filter(target_type=target_type,
                                               target_id=self.id,
                                               media_type=image_type)
        return media

    @property
    def videos(self):
        target_type = ContentType.objects.get_for_model(self)
        video_type = ContentType.objects.get_for_model(Video)
        media = AssociatedMedia.objects.filter(target_type=target_type,
                                               target_id=self.id,
                                               media_type=video_type)
        return media

class Book(PrimaryContent, Followable, Tagable, Renderable, Editable):
    TEMPLATE = 'renderables/book.html'
    MODEL_DEFAULT_FLAGS = 'overlay'

    user = models.ForeignKey(User, null=False, default=1)
    stream = models.ForeignKey(Stream, unique=True, null=True)
    moderators = models.ManyToManyField(User, related_name='moderator')

    file = models.FileField(upload_to='books/%Y/%m/%d')
    cover_image = models.ImageField(upload_to='images/%Y/%m/%d')
    isbn = models.CharField(max_length=255, null=True, blank=True)

    @property
    def link(self):
        return '/book/%s/%s/' % (self.id, urlsafe(self.title[:LIMIT]))
    
    @property
    def moderators_link(self):
        return '/book/moderators/%s/' % (self.id)
    
    @property
    def request_moderation_link(self):
        return '/book/request-moderation/%s/' % (self.id)
    
    @property
    def edit_link(self):
        return '/book/edit/%s/' % (self.id)

    def _get_book_data(self):
        data = []
        topics = self.node_set.filter(parent=None).order_by('order')

        for t in topics:
            data.append(t.get_json(0))

        return data

    @property
    def outline_json(self):
        data = self._get_book_data()
        return json.dumps(data)

    def _prepare_data(self, nodes, parent):
        flat_nodes = []

        for index, node in enumerate(nodes):
            _id = node['attributes'].get('id', None)
            _id = int(_id) if _id is not None else None
            node['attributes']['id'] = _id

            node['order'] = index
            node['parent'] = parent
            flat_nodes.append(node)

            children = node.get('children', [])
            flat_nodes.extend(self._prepare_data(children, node))

        return flat_nodes

    def _add_nodes(self, nodes):
        for index, node in enumerate(nodes):
            _id = node['attributes']['id']

            if _id is None:
                title = node['data']['title']
                order = node['order']
                parent = node['parent']
                if parent is not None:
                    p_id = parent['attributes']['id']
                    parent = Node.objects.get(id=p_id)

                n = Node.objects.create(title=title, book=self,
                                        parent=parent, order=order)
                node['attributes']['id'] = n.id

            children = node.get('children', [])
            self._add_nodes(children)

    def _delete_nodes(self, nodes):
        db_nodes = self.node_set.all()
        db_ids = set([n.id for n in db_nodes])
        cur_ids = set([n['attributes']['id'] for n in nodes])

        ids = db_ids - cur_ids

        for n in db_nodes:
            if n.id in ids:
                n.delete()

    def _update_nodes(self, nodes):
        db_nodes = dict([(n.id, n) for n in self.node_set.all()])

        for n in nodes:
            parent = n['parent']
            if parent is not None:
                parent = db_nodes[parent['attributes']['id']]

            _id = n['attributes']['id']
            db_node = db_nodes[_id]
            db_node.title = n['data']['title']
            db_node.order = n['order']
            db_node.parent = parent
            db_node.save()
    
    def update_json(self, data):
        nodes = json.loads(data)
        if not isinstance(nodes, list):
            nodes = [nodes]
        flat_nodes = self._prepare_data(nodes, None)
    
        self._add_nodes(nodes)
        self._update_nodes(flat_nodes)
        self._delete_nodes(flat_nodes)

    def is_editable_by(self, user):
        is_moderator = user in self.moderators.all()
        return Editable.is_editable_by(self, user) or is_moderator

class Node(PrimaryContent, Editable, Renderable):
    TEMPLATE = 'renderables/node.html'

    file = models.FileField(upload_to='nodes/%Y/%m/%d')
    book = models.ForeignKey(Book)
    parent = models.ForeignKey('self', null=True)
    order = models.IntegerField()

    class Meta:
        unique_together = ('title', 'parent', 'order')

    def is_editable_by(self, user):
        book = get_book(self)
        book_editable = False
        if book:
            book_editable = book.is_editable_by(user)
        return Editable.is_editable_by(self, user) or book_editable

    @property
    def link(self):
        return '/node/%s/%s/' % (self.id, urlsafe(self.title[:LIMIT]))

    @property
    def target(self):
        return self.book

    @property
    def subnodes(self):
        return Node.objects.filter(parent=self).order_by('order')

    def get_json(self, depth=0):
        data = {'attributes': {'id': self.id},
                'data': {
                            'title': self.title,
                            'attributes': {'class': 'edit-tree-node'},
                        },
               }
        if self.subnodes:
            data['state'] = 'open',
            data['children'] = [c.get_json(depth+1) for c in self.subnodes]

        return data

    def __unicode__(self):
        return '%s under %s' %(self.title, self.parent)

    @property
    def previous(self):
        if self.order == 0:
            return self.parent or self.book

        else:
            return Node.objects.get(parent=self.parent, book=self.book,
                order=self.order-1)

    @property
    def next(self):
        
        node = None

        try:
            return Node.objects.get(parent=self,
                                    book=self.book,
                                    order=0)
        except ObjectDoesNotExist:
            pass

        try:
            return Node.objects.get(parent=self.parent,
                                    book=self.book,
                                    order=self.order+1)

        except ObjectDoesNotExist:
            pass

        if self.parent:
            p = self.parent
            porder = p.order

            try:
                return Node.objects.get(parent=p.parent,
                                        book=p.book,
                                        order=porder+1)
            except ObjectDoesNotExist:
                pass

    def activity_count(self):
        '''
        Number of activities done on this node.
        (questions + nodes)
        '''
        return len(self.notes) + len(self.questions.all())

class AssociatedMedia(Content, RateFlag, Renderable):
    TEMPLATE = 'renderables/video.html'
    MODEL_DEFAULT_FLAGS = 'overlay'

    user = models.ForeignKey(User)
    
    target_type = models.ForeignKey(ContentType, related_name="target type")
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    media_type = models.ForeignKey(ContentType, related_name="media type")
    media_id = models.PositiveIntegerField(db_index=True)
    media = generic.GenericForeignKey('media_type', 'media_id')

    @classmethod
    def add(self, user, target, media):

        amedia = self.objects.create(user=user,
                            target_type=target.ctype,
                            target_id=target.id,
                            media_type=media.ctype,
                            media_id=media.id)
        return amedia
    
    @property
    def title(self):
        return self.media.title

    @property
    def link(self):
        amedia = 'video' if isinstance(self.media, Video) else 'image'
        return '/%s/%s/%s/' % (amedia, self.id, urlsafe(self.title[:LIMIT]))

    class Meta:
        unique_together = ('user', 'target_type', 'target_id', 'media_type', 'media_id')
        ordering = ('-score',)

    def __unicode__(self):
        return '%s of %s'  % (self.media, self.target)

class Ratings(Renderable, Referred, GroupRenderer):
    TEMPLATE = 'renderables/rating.html'
    GROUP_TEMPLATE = 'renderables/rating_group.html'

    UP = 1
    DOWN = -1

    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField()

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    @property
    def verb(self):
        return 'liked' if self.rating == self.UP else 'disliked'

    @classmethod
    def render_group(self, context, items):
       
        # group by user
        groups = groupby(items, lambda x: x.target.user)
        groups = [(k, list(citems)) for k, citems in groups]

        subgrouped = []
        for user, activities in groups:

            # group by rating
            activities.sort(key=lambda x: x.target.rating)
            activities = groupby(activities, lambda x: x.target.rating)
            activities = dict([(k, list(citems)) for k, citems in activities])

            subgroup = {'liked': activities.get(Ratings.UP, []),
                        'disliked': activities.get(Ratings.DOWN, [])}

            for rating, activities in subgroup.iteritems():
                # group by object type
                activities.sort(key=lambda x: x.target.target.__class__.__name__)
                activities = groupby(activities, lambda x: x.target.target.__class__.__name__)
                activities = dict([(k, list(citems)) for k, citems in activities])

                subgroup[rating] = activities

            if not subgroup['liked']:
                del subgroup['liked']
            
            if not subgroup['disliked']:
                del subgroup['disliked']

            subgrouped.append((user, subgroup))

        t = template.loader.get_template(self.GROUP_TEMPLATE)
        c = make_context(context)
        c['groups'] = subgrouped
        c['activities'] = items
        return t.render(c)

    class Meta:
        unique_together = ('user', 'target_id', 'target_type')

    def __unicode__(self):
        return '%s rated for %s'  % (self.user, self.target)

class Follows(Renderable, Referred):
    TEMPLATE = 'renderables/follow.html'

    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    @property
    def verb(self):
        return 'is now following'

    class Meta:
        unique_together = ('user', 'target_id', 'target_type')

    def __unicode__(self):
        return '%s for %s'  % (self.user, self.target)

class Flags(Renderable, Referred):
    TEMPLATE = 'renderables/flag.html'

    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)

    target_type = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField(db_index=True)
    target = generic.GenericForeignKey('target_type', 'target_id')

    @property
    def verb(self):
        return 'flagged'

    class Meta:
        unique_together = ('user', 'target_id', 'target_type')

    def __unicode__(self):
        return '%s for %s'  % (self.user, self.target)

class Video(Referred, Titled, Renderable):
    user = models.ForeignKey(User)
    date_added = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=100)
    source_id = models.CharField(max_length=200)

    def render(self, *args, **kwargs):
        return ''

    class Meta:
        unique_together = ('source', 'source_id')

    def __unicode__(self):
        return '%s for %s' %(self.source_id, self.title)
    
class Image(Referred, Titled):
    file = models.ImageField(upload_to='images/%Y/%m/%d')
    url_hash = models.CharField(max_length=32)
    url = models.TextField(max_length=2000)
    page_url = models.TextField(max_length=2000, blank=True, null=True)
    user = models.ForeignKey(User)

    class Meta:
        unique_together = ('url_hash',)
        
    def __unicode__(self):
        return '%s for %s' %(self.url, self.title)

    def save(self, *args, **kwargs):
        self.url_hash = hashlib.md5(self.url).hexdigest()
        super(Image, self).save(*args, **kwargs)

    @property
    def link(self):
        return '/image/%s/%s/' % (self.id, urlsafe(self.title[:LIMIT]))
