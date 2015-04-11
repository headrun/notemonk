# encoding: utf-8
'''
Activity system revamp. Need to populate stream per user and book.
'''
from django.contrib.contenttypes.models import ContentType
from core.models import *


def main():
    
    # Create Stream per user and book
    for u in UserProfile.objects.all():
        if u.stream is None:
            u.stream = Stream.objects.create(title='for user: %s' % u.user.username)
            u.save()

    for b in Book.objects.all():
        if b.stream is None:
            b.stream = Stream.objects.create(title='for book: %s' % b.title)
            b.save()

    # create stream entries for profile posts
    ppost_type = ContentType.objects.get_for_model(ProfilePost)
    for a in Activity.objects.filter(target_type=ppost_type).order_by('date_added'):
        p = a.target

        if p.profile.user == p.user:
            continue

        si = p.profile.stream.add(a)
        si.date_added = a.date_added
        si.save()

if __name__ == '__main__':
    main()
