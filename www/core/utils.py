import os
import re
import hashlib
import random
import urllib
import urllib2
import socket
import logging
from itertools import chain, islice

import feedparser

from django.contrib.contenttypes.models import ContentType
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.template import Context
from django.db.models.query import QuerySet
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
import django.core.mail as mail

socket.setdefaulttimeout(10)
log = logging.getLogger()
DEFAULT_USERAGENT = 'Mozilla/5.001 (windows; U; NT4.0; en-US; rv:1.0) Gecko/25250101'

HANDLING_CREDITS = 0

def xcode(string, encoding='utf8', mode='strict'):
    try:
        if isinstance(string, unicode):
            string = string.encode(encoding, mode)
        else:
            string = string.decode(encoding, mode)
    except:
        string = None

    return string

def urlsafe(string):
    string = xcode(string, 'ascii', 'ignore')
    string = string.replace('%', '')
    string = string.replace(' ', '.')
    string = string.replace('\'', '')
    string = string.replace('"', '')
    string = string.replace('?', '')
    return string

def get_doc(url, cache=None, user_agent=None):

    cache_id = hashlib.md5(url).hexdigest()
    data = None
    user_agent = user_agent or DEFAULT_USERAGENT

    if cache and isinstance(cache, (str, unicode)):
        cache = DirectoryCache(cache)

    request = urllib2.Request(url)
    request.add_header('User-Agent', user_agent)
    opener = urllib2.build_opener()

    if cache:
        data = cache.get(cache_id)
        
    if not data:
        data = opener.open(request).read()

    if cache:
       cache.set(cache_id, data)

    return data

class Cache:
    '''
    Represents a crawl cache
    '''
    def __init__(self):
        raise NotImplemented

    def get(self, id):
        '''
        Get data for specified id from cache
        @id (str)
        '''
        raise NotImplemented

    def set(self, id, data):
        '''
        Set data for specified id in cache
        @id (str)
        @data (str)
        '''
        raise NotImplemented

class DirectoryCache(Cache):
    '''
    A file system directory cache
    '''
    def __init__(self, cache_dir):
        '''
        @cache_dir (str) - location to store cache files / read from
        '''
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            raise Exception('Cache dir : %s not present' % cache_dir)

    def get_path(self, id):
        hash = hashlib.md5(id).hexdigest()
        dir_one = hash[:2]
        dir_two = hash[2:4]

        path = os.path.join(self.cache_dir, dir_one, dir_two)
        if not os.path.exists(path): os.makedirs(path)

        fpath = os.path.join(path, id)
        return fpath

    def get(self, id):
        path = self.get_path(id)
        data = None
        if os.path.exists(path):
            data = open(path).read()
        return data

    def set(self, id, data):
        path = self.get_path(id)
        assert(isinstance(data, str))
        open(path, 'w').write(data)

def _get_image_links(data):
    images = []

    data = re.findall('dyn.setResults\((.*?)\);</script>', data)[0]
    data = data[1:-1]
    data = eval(data)

    for item in data:
        #['/imgres?imgurl=http://musicalstewdaily.files.wordpress.com/2009/02/broken_heart_by_starry_eyedkid-1.jpg&imgrefurl=http://nappybrain.wordpress.com/&usg=__-DklieMA2JoqK37viOcmLC65k58=&h=872&w=947&sz=551&hl=en&start=21&itbs=1', '', 'M-QmlkObDYlaYM:', 'http://musicalstewdaily.files.wordpress.com/2009/02/broken_heart_by_starry_eyedkid-1.jpg', '148', '136', 'You broke my <b>heart</b> last night', '', '', '947 x 872 - 551k', 'jpg', 'nappybrain.wordpress.com', '', '', 'http://t2.gstatic.com/images', '1', [], '', 1, '', [], '']
        url = item[3]
        title = strip_tags(item[6])
        images.append([title, url])

    return images

def _get_image_links1(data):
    images = []
    _images = re.findall('imgurl=.*? height=', data)

    for i in _images:
        imglink = re.findall('imgurl=(.*?)&imgrefurl', i)[0]
        thumblink = re.findall('<img src=(.*):http', i)[0]
        images.append(['', imglink])

    return images

def get_gimages(sstring):
    log.debug('get_gimages: %s' % sstring)

    sstring = urllib.quote_plus(sstring)
    url = 'http://images.google.com/images?as_st=y&gbv=2&hl=en&'\
            'safe=active&tbo=1&sa=1&q=%s&aq=f&oq=&aqi=&start=0' % sstring
    data = get_doc(url, settings.CACHE_DIR, DEFAULT_USERAGENT)

    images = _get_image_links(data)
    if not images:
        images = _get_image_links1(data)

    return images

def get_ytvideos(sstring):
    log.debug('get_ytvideos: %s' % sstring)

    url = 'http://gdata.youtube.com/feeds/api/videos?orderby=relevance'\
            '&start-index=1&max-results=20&v=2&safeSearch=strict&q=%s'
    url = url % urllib.quote_plus(sstring)

    data = get_doc(url, settings.CACHE_DIR)
    feed = feedparser.parse(data)

    videos = []
    for e in feed.entries:
        title = e.title

        # FIXME: Some titles are being screwed by feedparser
        if not isinstance(title, unicode):
            try:
                title = title.xcode('utf8')
            except:
                continue


        # Sometimes the field of video id is different
        video_id = getattr(e, 'yt_videoid', None) or getattr(e, 'videoid', None)
        if not video_id:
            continue

        videos.append((title, video_id))

    log.debug('found %d videos' % len(videos))
    return videos

def get_target(target_type, target):
    target_type = ContentType.objects.get(id=int(target_type))

    try:
        target = target_type.get_object_for_this_type(id=int(target))
    except ObjectDoesNotExist:
        target = None

    return target

def get_target_from_req(req):
    target_type = req.POST['target_type']
    target = req.POST['target']

    return get_target(target_type, target)

def sanitize_whitespace(text):
    text = re.sub('\t+', ' ', text)
    text = re.sub('\n+', '\n', text)
    text = re.sub(' +', ' ', text)
    return text

def make_context(context):
    c = Context()
    keys = list(set(chain(*[d.keys() for d in context.dicts])))

    for k in keys:
        c[k] = context[k]

    return c

def parse_flags(flags):
    if not flags:
        return {}
    
    flags = [x.strip() for x in flags.split(',') if x.strip()]
    flags = [('is_' + x.split('-')[-1] if x.startswith('-') else 'is_' + x,
              not x.startswith('-')) for x in flags]
    flags = dict(flags)
    return flags

class QuerySetFilter(QuerySet):
    '''
    Filters a queryset and transforms the returned items
    using a user specified function. The fn is applied
    to every item and its return value is returned.

    If the fn returns None for a certain item, then that
    is filtered from the queryset
    '''

    def __init__(self, object_list, fn=lambda x: x):
        self.object_list = object_list
        self.fn = fn

    def __len__(self):
        return self.count()

    def count(self):
        return self.object_list.count()

    def __wrap_iter(self, iterator):
        for x in iterator:
            x = self.fn(x)
            if x is not None:
                yield x

    def __iter__(self):
        return self.__wrap_iter(iter(self.object_list))

    def __nonzero__(self):
        return self.object_list.__nonzero__()

    def all(self):
        return QuerySetFilter(self.object_list.all(), self.fn)

    def __getitem__(self, k):

        if k == 'count':
            return self.count()

        elif isinstance(k, slice):
            start, stop, step = k.indices(self.object_list.count())

            all = iter(self)
            items = []

            while len(items) < (stop - start):
                try:
                    items.append(all.next())
                except StopIteration:
                    break

            return items

        elif isinstance(k, int):
            return self.fn(self.object_list.__getitem__(int))
        
class QuerySetMerge(QuerySet):
    def __init__(self, querysets, key='-date_added'):
        self.querysets = querysets
        if key.startswith('-'):
            self.ascending = False
            self.key = key[1:]
        else:
            self.ascending = True
            self.key = key

    def xmerge(self, ln, ascending=True):
         """ Iterator version of merge.
     
         Assuming l1, l2, l3...ln sorted sequences, return an iterator that
         yield all the items of l1, l2, l3...ln in ascending order.
         Input values doesn't need to be lists: any iterable sequence can be used.
         """
        # Adapted from: http://code.activestate.com/recipes/141934-merging-sorted-sequences/

         pqueue = []
         for i in map(iter, ln):
             try:
                 pqueue.append((i.next(), i.next))
             except StopIteration:
                 pass
         pqueue.sort()
         if ascending:
             pqueue.reverse()
         X = max(0, len(pqueue) - 1)
         while X:
             d,f = pqueue.pop()
             yield d
             try:
                 # Insort in reverse order to avoid pop(0)
                 pqueue.append((f(), f))
                 pqueue.sort()
                 if ascending:
                     pqueue.reverse()
             except StopIteration:
                 X-=1
         if pqueue:
             d,f = pqueue[0]
             yield d
             try:
                 while 1: yield f()
             except StopIteration:pass

    def __len__(self):
        return self.count()

    def count(self):
        return sum(q.count() for q in self.querysets)

    def __iter__(self):
        qsets = [((getattr(x, self.key), x) for x in q) for q in self.querysets]
        merged = self.xmerge(qsets, self.ascending)
        return (x for k, x in merged)

    def __nonzero__(self):
        return self.count() != 0

    def all(self):
        return self

    def __getitem__(self, k):
        if k == 'count':
            return self.count()

        elif isinstance(k, slice):
            start, stop, step = k.indices(self.count())
            return islice(iter(self), start, stop, step)

class RoundRobinEmailBackend(SMTPEmailBackend):
    def __init__(self, *args, **kwargs):
        super(RoundRobinEmailBackend, self).__init__(*args, **kwargs)
        self.username = random.choice(settings.RR_EMAIL_USERS)

def get_md5(f):
    md5 = hashlib.md5()
    while True:
        chunk = f.read(128)
        if not chunk:
            break
        md5.update(chunk)
    return md5.hexdigest()

class StripCookieMiddleware(object):
    """Ganked from http://2ze.us/Io"""

    STRIP_RE = re.compile(r'\b(_[^=]+=.+?(?:; |$))')

    def process_request(self, request):
        cookie = self.STRIP_RE.sub('', request.META.get('HTTP_COOKIE', ''))
        request.META['HTTP_COOKIE'] = cookie
