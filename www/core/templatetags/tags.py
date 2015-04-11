import os
from decimal import Decimal
import hashlib
import colorsys

import Image as PIL

from django import template
from django.db.models.fields.files import FieldFile
from django.template import Library
from django.core.files.base import ContentFile
from django.conf import settings

from core.utils import get_doc, HANDLING_CREDITS, parse_flags
from core.models import *
from core.query import get_items_by_tag

NO_IMAGE = '/static/images/no_image_available.gif'
register = Library()

def C(context, c):
    c['request'] = context['request']
    c['user'] = context.get('user', '')
    c['ref_path'] = context.get('ref_path', '')
    return c

@register.inclusion_tag('ui/rate_widget.html', takes_context=True)
def rate(context, target):
    user = context['user'] 
    
    try:
        rating = target.ratings.get(user=user)
        rating = 'up' if rating.rating == Ratings.UP else 'down'
    except:
        rating = None

    return C(context, {'target': target, 'rating': rating})

@register.inclusion_tag('ui/follow_widget.html', takes_context=True)
def follow(context, target):
    user = context['user'] 
    
    try:
        followed = target.followed_by(user=user)
    except:
        followed = False

    return C(context, {'target': target, 'followed': followed})

@register.inclusion_tag('ui/flag_widget.html', takes_context=True)
def flag(context, target):
    user = context['user'] 
    ref_path = context['ref_path'] 
    try:
        flagged = target.flaggers.get(user=user)
    except:
        flagged = False

    return C(context, {'target': target, 'flagged': flagged})

@register.inclusion_tag('ui/bookshelf_widget.html', takes_context=True)
def bookshelf(context, title, query_type, tags, no_items):
    tags = [t.strip() for t in tags.split(',')]
    books = get_items_by_tag(Book, tags, query_type)

    more_link = ''
    if books.count() > no_items:
        tags = '/'.join(tags)
        more_link = '/books/tag/%(query_type)s/%(tags)s/' % locals()

    return C(context, {'title': title, 'books': books[:no_items],
            'more_link': more_link})

@register.inclusion_tag('ui/note_widget.html', takes_context=True)
def note(context, target):
    user = context['user']
    user_note = target.user_note(user)
    return C(context, {'user_note': user_note, 'target': target})

@register.inclusion_tag('ui/question_widget.html', takes_context=True)
def question(context, target, topic, num):
    markup_widget_id = 'question_text_%d_%d' % (target.ctype.id, target.id)
    return C(context, {'target': target, 'topic': topic, 'num_questions': num,
            'questions': target.questions.all()[:num],
            'markup_widget_id': markup_widget_id})

@register.inclusion_tag('ui/profilepost_widget.html', takes_context=True)
def profilepost(context, target, topic, num):
    return C(context, {'target': target, 'topic': topic, 'num_posts': num,
            'posts': target.questions.all()[:num]})

@register.inclusion_tag('ui/bad_script.html', takes_context=True)
def background_ad(context, book):
    tags = [t.tag.name for t in book.tags.all()]
    show_ad = False

    if 'NCERT' in tags or 'CBSE' in tags or 'Tamil Nadu' in tags:
        if '6th' in tags or '7th' in tags or '8th' in tags or '9th' in tags or '10th' in tags:
            show_ad = False

    return C(context, {'show_ad': show_ad, 'tags': tags})

@register.inclusion_tag('ui/comment_widget.html', takes_context=True)
def comment(context, target, flags=None):
    flags = parse_flags(flags)

    return C(context, {'target': target, 'flags': flags})

@register.inclusion_tag('ui/outline_widget.html', takes_context=True)
def outline(context, node, depth):
    subnodes = Node.objects.filter(parent=node).order_by('order')
    return C(context, {'depth': depth + 1, 'node': node, 'subnodes': subnodes})

@register.inclusion_tag('ui/paginator_widget.html', takes_context=True)
def paginator(context, items, paging_url):
    previous_link = paging_url.replace('<PAGENO>',
        str(items.previous_page_number()))

    next_link = paging_url.replace('<PAGENO>',
        str(items.next_page_number()))

    return C(context, {'items': items, 'previous_link': previous_link,
            'next_link': next_link})

@register.inclusion_tag('ui/preview_widget.html', takes_context=True)
def preview_attachment(context, url):
    if url.lower().endswith('xlsx') or url.lower().endswith('doc') or \
        url.lower().endswith('docx') or url.lower().endswith('pdf'):
            url = ' http://viewer.docspad.com/index.php?doc=%s&key=US3Lx8KlveTOzgYS' %url
    else:
        url = ''

    return C(context, {'url':url})

@register.inclusion_tag('ui/cart_widget.html', takes_context=True)
def cart(context):
    req = context['request']
    user = context['user']
    if user.is_anonymous():
        return ''
        
    show_checkout_link = not req.get_full_path().startswith('/cart/checkout/')
    
    cart_data = req.session.setdefault('cart', [])
    cart = []
    total_credits = Decimal('0.0')

    for item, num in cart_data:
        item = RedeemableItem.objects.get(id=int(item))
        item.opts = range(1, item.num + 1)
        cart.append((item, num))
        item_credits = item.credits * num
        item.item_credits = item_credits
        total_credits += item_credits

    total_credits = total_credits + HANDLING_CREDITS
    
    available_credits = user.get_profile().credits - total_credits
    sufficient_credits = (available_credits >= 0)

    data = {
            'cart': cart,
            'total_credits': total_credits,
            'available_credits': available_credits.copy_abs(),
            'handling_credits': HANDLING_CREDITS,
            'sufficient_credits': sufficient_credits,
            'checkout_link': show_checkout_link,
           }
    return C(context, data)

@register.inclusion_tag('ui/markitup_editor.html', takes_context=True)
def markup(context, widget_id, target):
    return C(context, {'widget_id': widget_id, 'target': target})

@register.inclusion_tag('ui/attachments_widget.html', takes_context=True)
def attachments(context, target, num):
    user = context['user']
    can_add = target.is_editable_by(user)
    return C(context, {'target': target, 'num': num, 'can_add': can_add})

def render(parser, token):
    contents = token.split_contents()
    tag_name = contents.pop(0)
    
    if len(contents) < 1:
        raise template.TemplateSyntaxError, "%r tag requires atleast one argument" % tag_name

    return RenderObj(contents)

class RenderObj(template.Node):
    def __init__(self, contents):
        self.contents = contents

    def render(self, context):
        resolved_contents = []
        
        for c in self.contents:
            resolved_contents.append(template.Variable(c).resolve(context))
        
        obj = resolved_contents.pop(0)
        if obj is None:
            return ''
        
        return obj.render(context, *resolved_contents)

register.tag('render', render)

def button(parser, token):
    args = token.split_contents()
    tag_name = args.pop(0)
    
    if len(args) < 1:
        raise template.TemplateSyntaxError, "%r tag atleast one argument" % tag_name

    link = args.pop(0)[1:-1]
    kwargs = dict([a.strip('\'').split('=', 1) for a in args])

    nodelist = parser.parse(('endbutton',))
    parser.delete_first_token()

    return Button(nodelist, link, kwargs)

class Button(template.Node):
    DEFAULTS = {
        'title': 'Click Here',
        'color': '7E9BDE',
        'hcolor': 'DEDEDE',
        'borderwidth': '1px',
        }

    def _ensure_range(self, val, min, max):
        if val < min: return min
        if val > max: return max
        return val

    def _get_text_color(self, color):
        rgb = self._htmlcolor_to_rgb(color)
        rgb = self._norm_rgb(rgb)
        h, s, v = colorsys.rgb_to_hsv(*rgb)

        text_v = .9 if v < .7 else .1
        text_v = self._ensure_range(text_v, 0, 1)
        
        rgb = colorsys.hsv_to_rgb(h, 0.2, text_v)
        rgb = self._denorm_rgb(rgb)
        return self._rgb_to_htmlcolor(rgb)

    def _norm_rgb(self, rgb):
        r, g, b = rgb
        r = r / 255.
        g = g / 255.
        b = b / 255.
        return r, g, b

    def _denorm_rgb(self, rgb):
        r, g, b = rgb
        r = r * 255
        g = g * 255
        b = b * 255
        return r, g, b

    def _get_lighter_color(self, htmlcolor, percent=.1):
        rgb = self._htmlcolor_to_rgb(htmlcolor)
        rgb = self._norm_rgb(rgb)
        h, s, v = colorsys.rgb_to_hsv(*rgb)
        v = v + v * percent
        rgb = colorsys.hsv_to_rgb(h, s, v)
        rgb = self._denorm_rgb(rgb)
        return self._rgb_to_htmlcolor(rgb)

    def _get_darker_color(self, htmlcolor, percent=.1):
        rgb = self._htmlcolor_to_rgb(htmlcolor)
        rgb = self._norm_rgb(rgb)
        h, s, v = colorsys.rgb_to_hsv(*rgb)
        v = v - v * percent
        rgb = colorsys.hsv_to_rgb(h, s, v)
        rgb = self._denorm_rgb(rgb)
        return self._rgb_to_htmlcolor(rgb)

    def _rgb_to_htmlcolor(self, rgb):
        r, g, b = [int(self._ensure_range(v, 0, 255)) for v in rgb]
        return '%s%s%s' % (hex(r)[2:], hex(g)[2:], hex(b)[2:])

    def _htmlcolor_to_rgb(self, htmlcolor):
        h = htmlcolor.strip(' #')
        r, g, b = h[:2], h[2:4], h[4:6]
        r = eval('0x' + r)
        g = eval('0x' + g)
        b = eval('0x' + b)
        return r, g, b

    def __init__(self, nodelist, link, kwargs):
        self.nodelist = nodelist
        self.link = link
        self.kwargs = kwargs

    def render(self, context):
        t = template.loader.get_template('ui/button_widget.html')

        button_text = self.nodelist.render(context)
        button_class = 'btncl_' + hashlib.md5(self.link).hexdigest()

        for k, v in self.kwargs.iteritems():
            self.kwargs[k] = template.Template(v).render(context)

        c = make_context(context)
        c['link'] = template.Template(self.link).render(context)
        c['buttontext'] = button_text
        c['button_class'] = button_class

        k = dict(self.kwargs)
        D = self.DEFAULTS

        k['title'] = k.get('title') or D['title']
        k['color'] = k.get('color') or D['color']
        k['hcolor'] = k.get('hcolor') or D['hcolor']
        k['borderwidth'] = k.get('borderwidth') or D['borderwidth']

        k['tcolor'] = k.get('tcolor') or self._get_text_color(k['color'])
        k['htcolor'] = k.get('htcolor') or self._get_text_color(k['hcolor'])
        
        k['blight'] = k.get('blight') or self._get_lighter_color(k['color'], .3)
        k['bdark'] = k.get('bdark') or self._get_darker_color(k['color'], .3)
        
        k['hblight'] = k.get('hblight') or self._get_lighter_color(k['hcolor'], .3)
        k['hbdark'] = k.get('hbdark') or self._get_darker_color(k['hcolor'], .3)

        kwargs = k

        for k, v in kwargs.iteritems():
            c[k] = v

        c = C(context, c)

        return t.render(c)

register.tag('button', button)

def thumbnail(obj, size='104x104'):

    square = False
    arg_size = size
    if size.startswith('S'):
        square = True
        size = size[1:]
        crop = True

    if isinstance(obj, AssociatedMedia):
        image = obj.media

        if not image.file:
            try:
                content = get_doc(image.url, settings.CACHE_DIR)
            except:
                obj.delete()
                return thumbnail(NO_IMAGE , size)

            content_file = ContentFile(content)
            fname = hashlib.md5(image.url).hexdigest() + '.' + image.url.rsplit('.', 1)[-1]
            image.file.save(fname, content_file, save=True)

        file = image.file
        path = file.path
        url = file.url

    elif isinstance(obj, FieldFile):
        file = obj
        path = file.path
        url = file.url

    elif isinstance(obj, (str, unicode)):
            file_path = obj
            file_path = file_path.split('static', 1)[-1]
            path = settings.MEDIA_ROOT + file_path
            url = settings.MEDIA_URL + file_path
    else:
        return thumbnail(NO_IMAGE , size)

    # defining the size
    dimensions = [int(x) if x.isdigit() else None for x in size.lower().split('x')]

    # defining the filename and the miniature filename
    filehead, filetail = os.path.split(path)
    basename, format = os.path.splitext(filetail)
    miniature = basename + '_' + size + format
    filename = path
    miniature_filename = os.path.join(filehead, miniature)
    filehead, filetail = os.path.split(url)
    miniature_url = filehead + '/' + miniature

    if os.path.exists(miniature_filename) and os.path.getmtime(filename) > os.path.getmtime(miniature_filename):
        os.unlink(miniature_filename)

    # if the image wasn't already resized, resize it
    if not os.path.exists(miniature_filename):
        
        try:
            image = PIL.open(filename)
        except IOError:
            if isinstance(obj, AssociatedMedia):
                obj.delete()
            return thumbnail(NO_IMAGE , size)

        format = image.format

        if image.mode != 'RGBA' and format != 'BMP':
            image = image.convert('RGBA')
    
        if square:
            width, height = image.size
            side = min(width, height)
            x = (width - side) / 2
            y = (height - side) / 2
            image = image.crop((x, y, x+side, y+side))

        try:
            image.thumbnail(dimensions, PIL.ANTIALIAS)
            image.save(miniature_filename, format, quality=90)
        except:
            return thumbnail('/static/images/user.png', arg_size)

    return miniature_url
    
register.filter(thumbnail)
