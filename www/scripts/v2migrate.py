# encoding: utf-8
import os
import datetime
import hashlib
from core.utils import QuerySetMerge, QuerySetFilter
from django.core.files.base import ContentFile
from django.contrib.contenttypes.models import ContentType
from core.models import *


def main():

    # Ensure Markup rendered field is filled in
    # By force saving all models
    for k in (Question, Answer, Note):
        for o in k.objects.all():
            o.save()

    # Prepopulate activities into Activity table
    qsets = []
    for k in (PointsHistory, Book, Note, Question, Answer,
              Ratings, Follows, Flags, Redemption, Attachment,
              Comment, ProfilePost):
        qsets.append(k.objects.all().order_by('-date_added'))

    qsets.append(QuerySetFilter(AssociatedMedia.objects.all().order_by('date_added'),
                    fn=lambda x: (x if isinstance(x.media, Video) else None)))
    qset = QuerySetMerge(qsets, 'date_added')

    for o in qset:
        a = Activity.add(o.user, o)
        if a is None: continue
        a.date_added = o.date_added
        a.save()

    # Convert Q&A in user pages into ProfilePosts and Comments

    uprofile_ctype = ContentType.objects.get_for_model(UserProfile)

    questions = Question.objects.filter(target_type=uprofile_ctype.id).order_by('-date_added')
    for q in questions:
        pp = ProfilePost.objects.create(user=q.user, profile=q.target,
                text=q.text.raw)
        pp.date_added = q.date_added
        pp.save()

        answers = q.answer_set.all().order_by('-date_added')
        for a in answers:
            Comment.objects.create(user=a.user, text=a.text.raw,
                target_type=pp.ctype, target_id=pp.id)


    # Make book download into attachment
    for b in Book.objects.all().order_by('-date_added'):
        if not b.file: continue
        if not os.path.exists(b.file.path): continue
        c = open(b.file.path, 'rb').read()
        checksum = hashlib.md5(c).hexdigest()
        c = ContentFile(c)

        u = UploadedFile(checksum=checksum, uploader=b.user)
        u.file.save(b.file.name, c, save=True)
        u.save()

        a = b.attach(b.user, ufile=u, title='FULL NCERT BOOK - ZIP')


    def backwards(self, orm):
        pass


if __name__ == '__main__':
    main()
