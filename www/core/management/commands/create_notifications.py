from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_noop as _
from notification import models as notification

class Command(BaseCommand):
    help = 'Creates notification types. Run once at installation time.'
    args = ''

    def handle(self, *args, **options):
        create = notification.create_notice_type
        create('question_add', _('Question Added'), _('A new question has been added'))
        create('question_rated', _('Question Rated'), _('Question has been rated'))
        create('answer_add', _('Answer Added'), _('A new answer has been added'))
        create('answer_rated', _('Answer Rated'), _('Answer has been rated'))
        create('video_add', _('Video Added'), _('A new video has been added'))
        create('video_rated', _('Video Rated'), _('Video has been rated'))
        create('note_add', _('Notes Added'), _('Notes has been added'))
        create('note_rated', _('Note Rated'), _('Note has been rated'))
        create('note_changed', _('Note Changed'), _('Note has been changed'))
        create('profile_changed', _('Profile Changed'), _('Profile has been changed'))
        create('profile_rated', _('Profile Rated'), _('Profile has been rated'))
        create('book_rated', _('Book Rated'), _('Book has been rated'))
        create('node_rated', _('Topic Rated'), _('Topic has been rated'))
        create('user_level_changed', _('Level Changed'), _('Level has changed'))
        create('book_mod_request', _('Book Mod Requested'), _('A user has requested permissions to moderate book'))
        create('credits_earned', _('Credits Earned'), _('You have earned credits'))
        create('user_redeemed', _('User Redeemed'), _('User has redeemed credits'))
        create('comment_add', _('Commented'), _('A new comment has been added'))
        create('ppost_add', _('New Profile Post'), _('A new post has been made on a profile'))

        create('_user_joined', _('User Joined'), _('A new user has been joined'))
        create('_user_feedback', _('User Feedback'), _('Feedback from user'))

    def usage(self, subcommand):
        return ''
