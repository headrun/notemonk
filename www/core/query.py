from django.db import IntegrityError
from django.contrib.contenttypes.models import ContentType
from django.db import connection

from core.models import *
from core.utils import get_gimages, get_ytvideos
from core.utils import log, xcode

def get_top_users(limit=20):
    #return UserProfile.objects.filter(user__is_staff=False).order_by('-points')[:limit]
    toppers = Toppers.objects.order_by('id')
    return [t.user_profile for t in toppers]

def load_images(node, user):
    log.debug('load_images: %s, %s' % (node, user))

    images = get_gimages(xcode(node.title, mode='ignore'))
    I = Image.objects

    for title, url in images:
        try:
            image = I.create(title=title, url=url, user=user)
        except IntegrityError:
            image = I.get(url=url)

        try:
            aimage = AssociatedMedia.add(user, node, image)
        except IntegrityError:
            pass

def load_videos(node, user):
    title = xcode(node.title, mode='ignore')
    videos = get_ytvideos(title)

    V = Video.objects

    for title, yt_id in videos:

        log.debug('Adding video: %s, %s ...' % (yt_id, title))

        try:
            video = V.create(source='youtube', source_id=yt_id,
                             user=user, title=title)
        except IntegrityError:
            log.debug('Video exists already')
            video = V.get(source='youtube', source_id=yt_id)

        try:
            avideo = AssociatedMedia.add(user, node, video)
        except IntegrityError:
            pass

def get_items_by_tag(model, tags, query_type='all'):
    item_type = ContentType.objects.get_for_model(model).id

    tags = [str(t.id) for t in Tag.objects.filter(name__in=tags)]
    if not tags:
        return model.objects.none()

    query = '''SELECT item_id FROM core_tagitem
            WHERE item_type_id = %s AND tag_id IN (%s)
            GROUP BY item_id '''

    if query_type == 'all':
        query = query + 'HAVING COUNT(item_id) = %s'
        params = (item_type, ','.join(tags), len(tags))

    else:
        params = (item_type, ','.join(tags))

    query = query % params
    cursor = connection.cursor()
    cursor.execute(query)

    item_ids = [row[0] for row in cursor.fetchall()]
    objs = model.objects
    return objs.filter(id__in=item_ids) if item_ids else objs.none()
