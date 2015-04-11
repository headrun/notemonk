#!/usr/bin/env python
import re
import sys
from pprint import pprint

from core.models import *
from django.core.files.base import ContentFile

def parse_book_data(book):
    book = book.strip().split('\n')
    name = book[0]
    book_file = book[1]
    image_file = book[2]
    
    data = book[3:]
    data = _parse_book_data(data, 0, 0)
    return name, book_file, image_file, data

def _parse_book_data(data, index, prev_indent):

    out = []

    cur_indent = prev_indent
    for index, d in enumerate(data):
        if d is None:
            continue
        cur_indent = len(re.findall('^ *', d)[0])
        if cur_indent > prev_indent:
            cdata = _parse_book_data(data, index, cur_indent)
            out[-1][1].extend(cdata)
        elif cur_indent == prev_indent:
            out.append([d.strip(), []])
            data[index] = None
        else:
            return out

    return out

def add_to_db(name, book_file, image_file, outline):
    b = Book.objects.create(title=name, followcount=0, flagcount=0)
    content = ContentFile(open(book_file, 'rb').read())
    thumbnail = ContentFile(open(image_file, 'rb').read())
    
    b.file.save(name+'.zip', content, save=True)
    b.cover_image.save(name+'.jpg', thumbnail, save=True)    
    _add_to_db(b, outline, None)

def _add_to_db(book, data, parent):
    for index, (node, children) in enumerate(data):
        try: print 'Node: ', node
        except: pass
        n = Node.objects.create(title=node, parent=parent,
                                book=book, order=index)
        _add_to_db(book, children, n)

def main(stream):
    books = stream.read().strip().split('\n\n')

    for book in books:
        name, book_file, image_file, outline = parse_book_data(book)
        try: print 'Book: ', name
        except: pass
        add_to_db(name, book_file, image_file, outline)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'usage: python %s <book-data-file>' % sys.argv[0]
        sys.exit(1)

    books_data_file = sys.argv[1]
    stream = open(books_data_file).read()
    main(stream)
