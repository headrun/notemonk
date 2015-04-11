from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings
from django.contrib.auth.views import password_reset, password_reset_done
from django.contrib.auth.views import password_reset_confirm, password_reset_complete
from django.views.decorators.cache import cache_page

# Pagination url regular expression that extracts
# page_no and num from the url if present
P = '(?:(?P<page_no>[0-9]+)/(?:(?P<num>[0-9]+)/){0,1}){0,1}'

# Generic Target Url Fragment
T = '(?P<target_type>[0-9]+)/(?P<target>[0-9]+)'

# Username capture Url Fragment
U = '(?P<username>[:_\.\-A-Za-z0-9]+)'

admin.autodiscover()

handler500 = 'core.views.handler_500'
handler404 = 'core.views.handler_404'

urls = patterns('core.views',
    url(r'^admin/', include(admin.site.urls)),

    url(r'^ncert/$', 'ncert_view', name='ncert_page'),
    url(r'^tamilnadu/$', 'tamilnadu_view', name='tamilnadu_page'),
    url(r'^bits_msss/$', 'bits_view', name='bits_page'),
    url(r'^anu_books/$', 'anu_view', name='anu_page'),
    url(r'^ipe_books/$', 'ipe_view', name='ipe_page'),
    url(r'^cbse_books/$', 'cbse_view', name='cbse_page'),
    url(r'^aieee_books/$', 'aieee_view', name='aieee_page'),
    url(r'^iitjee_books/$', 'iitjee_view', name='iitjee_page'),
    url(r'^upsc_books/$', 'upsc_view', name='upsc_page'),

    # background ad popup version page [ bad.html  ]
    url(r'^bad/$', 'bad_view', name='bad_page'),


    url(r'^$', 'home_view', name='home_page'),
    url(r'', include('social_auth.urls')),
    url(r'^login/$', 'login_view', name='login_page'),
    url(r'^logout/$', 'logout_user'),
    url(r'^fb_login/$', 'fb_login'),
    url(r'^accounts/profile/$', 'user_view'),
    
    url(r'^invite/$', 'invite_view'),
    url(r'^email/$', 'email_view', name='email_page'),

    url(r'^tags/$', 'tags_view'),

    url(r'^user/$', 'user_view'),
    url(r'^user/edit/$', 'user_edit_view', name='user_edit_page'),
    url(r'^user/%s/(?:(?P<a_id>[0-9]+)/){0,1}$' % U, 'user_view', name='user_page'),
    url(r'^user/%s/(?P<filter>[a-z_]+)/%s$' % (U, P), 'user_items_view', name='user_items_page'),
    
    url(r'^books/$', 'books_view', name='books_page'),
    url(r'^books/recent/%s$' % P, 'books_recent_view', name='books_recent_page'),
    url(r'^books/popular/%s$' % P, 'books_popular_view', name='books_popular_page'),
    url(r'^books/tag/(?P<tag>[^/]+)/%s$' % P, 'books_tag_view', name='books_tag_page'),
    url(r'^books/tag/all/(?P<tags>.*?)/%s$' % P, 'books_tag_all_view', name='books_tag_all_page'),
    url(r'^books/tag/any/(?P<tags>.*?)/%s$' % P, 'books_tag_any_view', name='books_tag_any_page'),
    
    url(r'^book/add/$', 'book_add_view', name='book_add_page'),
    url(r'^book/edit/(?P<book_id>[0-9]+)/$', 'book_edit_view', name='book_edit_page'),
    url(r'^book/(?P<book_id>[0-9]+)/', 'book_view', name='book_page'),
    url(r'^book/moderators/(?P<book_id>[0-9]+)/%s$' % P, 'book_moderators_view', name='book_moderators_page'),
    url(r'^book/request-moderation/(?P<book_id>[0-9]+)/$', 'book_request_moderation_view', name='book_moderation_page'),
    url(r'^book/confirm-moderation/(?P<book_id>[0-9]+)/%s/$' % U,
            'book_confirm_moderation_view', name='book_confirm_moderation_page'),

    url(r'^node/(?P<node_id>[0-9]+)/', 'node_view', name='node_page'),
    url(r'^video/(?P<avideo_id>[0-9]+)/', 'video_view', name='video_page'),
    url(r'^attachment/(?P<attachment_id>[0-9]+)/', 'attachment_view', name='attachment_page'),
    url(r'^attachment/edit/(?P<attachment_id>[0-9]+)/', 'attachment_edit_view', name='attachment_edit_page'),
    url(r'^attachment/add/%s/$' % T, 'attachment_add_view'),
    url(r'^image/(?P<image_id>[0-9]+)/', 'image_view', name='image_page'),

    url(r'^note/(?P<note_id>[0-9]+)/$', 'note_view', name='note_page'),
    url(r'^note/(?P<note_id>[0-9]+)/edit/$', 'note_edit_view', name = 'note_edit_page'),
    url(r'^note/(?P<note_id>[0-9]+)/revisions/%s$' % P, 'note_edit_view'),
    url(r'^note/(?P<note_id>[0-9]+)/revision/(?P<revision_id>[0-9]+)/$', 'note_revision_view', name='note_revision_page'),
    url(r'^note/(?P<note_id>[0-9]+)/revision/(?P<revision_id>[0-9]+)/revert/$', 'note_revision_revert_view', name='note_revision_revert_page'),

    url(r'^qa/question/$', 'question'),
    url(r'^qa/answer/$', 'answer'),
    url(r'^qa/question/(?P<q_id>[0-9]+)/', 'question_view'),

    url(r'^add/video/$', 'add_video'),
    url(r'^add/image/$', 'add_image'),
    url(r'^add/note/$', 'add_note'),

    url(r'^questions/%s/%s' % (T, P), 'questions_view'),
    url(r'^images/%s/%s' % (T, P), 'images_view'),
    url(r'^videos/%s/%s' % (T, P), 'videos_view'),
    url(r'^attachments/%s/%s' % (T, P), 'attachments_view'),
    url(r'^notes/%s/%s' % (T, P), 'notes_view'),

    url(r'^activities/all/(?:(?P<a_id>[0-9]+)/){0,1}$', 'activities_view'),
   
    url(r'^(?P<u_items>[a-z]+)/all/(?P<order>[a-z]+)/%s$' % P, 'allitems_view'),
    
    url(r'^up/%s/%s' % (T, P), 'uppers_view'),
    url(r'^down/%s/%s' % (T, P), 'downers_view'),
    url(r'^followers/%s/%s' % (T, P), 'followers_view'),

    url(r'^users/%s' % P, 'users_view'),
    url(r'^insert_image/(?:%s/){0,1}$' % T, 'insert_image_view'),

    url(r'^redeemables/%s$' % P, 'redeemables_view'),
    url(r'^redeemable/(?P<item_id>[0-9]+)/', 'redeemable_view'),
    url(r'^redemption/(?P<r_id>[0-9]+)/$', 'redemption_view', name='redemption_page'),
    url(r'^cart/add/(?P<item_id>[0-9]+)/(?:(?P<num_items>[0-9]+)/){0,1}$', 'cart_add_view'),
    url(r'^cart/remove/(?P<item_id>[0-9]+)/$', 'cart_remove_view'),
    url(r'^cart/checkout/$', 'cart_checkout_view'),

    url(r'^rate/$', 'rate'),
    url(r'^follow/$', 'follow'),
    url(r'^flag/$', 'flag'),

    url(r'^comment/add/%s/$' % T, 'comment_add_view'),
    url(r'^comment/edit/(?P<comment_id>[0-9]+)/$', 'comment_edit_view'),

    url(r'^profilepost/(?P<profilepost_id>[0-9]+)/$', 'profilepost_view'),
    url(r'^profilepost/add/(?P<profile_id>[0-9]+)/$', 'profilepost_add_view'),
    url(r'^profilepost/edit/(?P<post_id>[0-9]+)/$', 'profilepost_edit_view'),
   
    url(r'^privacy_policy/$', 'privacy_policy_view'),
    url(r'^feedback/$', 'feedback_view'),
    url(r'^feedback/sent/$', 'feedback_sent_view', name='feedback_sent_page'),
    
    url(r'^xd_receiver\.htm$', 'xd_receiver_view'),
    
    )

urlpatterns = urls + patterns('',
    (r'^markitup/', include('markitup.urls')),
    (r'^notification/$', 'django.views.generic.simple.redirect_to', {'url': '/user/edit/'}),
    (r'^notification/', include('notification.urls')),
    (r'^accounts/password/reset/$', password_reset, {'template_name': 'registration/_password_reset.html'}),
    (r'^accounts/password/reset/done/$', password_reset_done, {'template_name': 'registration/_password_reset_done.html'}),
    (r'^accounts/password/reset/confirm/$', password_reset_confirm, {'template_name': 'registration/_password_reset_confirm.html'}),
    (r'^accounts/password/reset/confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', password_reset_confirm, {'template_name': 'registration/_password_reset_confirm.html'}),
    (r'^accounts/password/reset/complete/$', password_reset_complete, {'template_name': 'registration/_password_reset_complete.html'}),
    (r'^accounts/', include('registration.backends.default.urls')),
    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/images/favicon-32x32.ico'}),
    (r'^robots\.txt$', 'django.views.generic.simple.redirect_to', {'url': '/static/files/robots.txt'}),
    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
                 {'document_root': settings.MEDIA_ROOT}),
    (r'^media/(?P<path>.*)$', 'django.views.static.serve',
                 {'document_root': settings.ADMIN_MEDIA_ROOT}),
    (r'^redeem/$', 'django.views.generic.simple.redirect_to', {'url': '/redeemables/'}),
)
