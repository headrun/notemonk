#!/usr/bin/env python

from core.models import Tag
from django.db import IntegrityError

def main(tags_fname):
    Tag.objects.all().delete()

    tags = set([t.strip() for t in open(tags_fname)\
        if t.strip() and not t.strip().startswith('#')])

    for tag in tags:
        Tag.objects.create(name=tag)

if __name__ == '__main__':
    main(sys.argv[1])
