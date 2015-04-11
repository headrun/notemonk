import urllib2

from django.contrib.auth.models import User
from django.core.files.base import ContentFile

from core.models import FBUserProfile

class FacebookBackend:
    def authenticate(self, request):
        fb_user = request.facebook.users.getLoggedInUser()
        
        try:
            profile = FBUserProfile.objects.get(uid=str(fb_user))
            return profile.user
        except FBUserProfile.DoesNotExist:
            fb_data = request.facebook.users.getInfo([fb_user], ['uid',
                                                     'username', 'email', 'about_me',
                                                     'first_name', 'last_name',
                                                     'pic_big', 'pic', 'pic_small',
                                                     'current_location', 'profile_url'])

            if not fb_data:
                return None

            fb_data = fb_data[0]
            username = 'fb.%s' % (fb_data['username'] or fb_data['uid'])
            user_email = fb_data['email'] or ''
            user = User.objects.create(username=username)
            user.first_name = fb_data['first_name']
            user.last_name = fb_data['last_name']
            user.save()

            FBUserProfile.objects.create(uid=str(fb_user), user=user)

            user_profile = user.get_profile()

            location = fb_data['current_location']
            if location:
                user_profile.city = location['city']
                user_profile.state = location['state']
                user_profile.country = location['country']
                user_profile.save()

            image_url = fb_data['pic_big']
            if image_url:
                try:
                    image_ext = image_url.rsplit('.', 1)[-1]
                except IndexError:
                    image_ext = 'jpg'
                    
                image = urllib2.urlopen(image_url)
                cfile = ContentFile(image.read())
                
                image_name = '%s.%s' % (username, image_ext)
                user_profile.image.save(image_name, cfile, save=True)

            return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None