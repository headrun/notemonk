import new

from django import forms
from django.forms import ValidationError
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User

from recaptcha.client import captcha
from core.forms import RegistrationForm
from registration.views import register as register_view
from registration.backends.default import DefaultBackend as RegDefaultBackend

class RegBackend(RegDefaultBackend):
    def register(self, request, **kwargs):
        new_user = RegDefaultBackend.register(self, request, **kwargs)
        referrer = kwargs['referrer']
        if referrer:
            try:
                referrer = User.objects.get(username=referrer)
                new_user_p = new_user.get_profile()
                referrer_p = referrer.get_profile()

                new_user_p.referrer = referrer

                new_user_p.follow(referrer)
                new_user_p.save()

                referrer_p.follow(new_user)
                referrer_p.save()
            except ObjectDoesNotExist:
                pass

        return new_user

class RecaptchaMiddleware:
    def process_view(self, request, view_func, view_args, view_kwargs):
        if view_func == register_view:
            klass = new.classobj('SafeForm', (RegistrationForm, RecaptchaForm),
                                    {'REQUEST': request})

            referrer = request.GET.get('referrer', None)
            if referrer:
                klass.base_fields['referrer'].initial = referrer

            view_kwargs['form_class'] = klass
            view_kwargs['backend'] = 'core.recaptcha_form.RegBackend'

class RecaptchaWidget(forms.Widget):
    """ A Widget which "renders" the output of captcha.displayhtml """
    def render(self, *args, **kwargs):
        return captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY)

class DummyWidget(forms.Widget):
    """
    A dummy Widget class for a placeholder input field which will
    be created by captcha.displayhtml

    """
    # make sure that labels are not displayed either
    is_hidden=True
    def render(self, *args, **kwargs):
        return ''

class RecaptchaForm(forms.Form):
    """ 
    A form class which uses reCAPTCHA for user validation.
    
    If the captcha is not guessed correctly, a ValidationError is raised
    for the appropriate field
    """
    recaptcha_challenge_field = forms.CharField(widget=DummyWidget)
    recaptcha_response_field = forms.CharField(widget=RecaptchaWidget, label='')

    def clean_recaptcha_response_field(self):
        if 'recaptcha_challenge_field' in self.cleaned_data:
            self.validate_captcha()
        return self.cleaned_data['recaptcha_response_field']

    def clean_recaptcha_challenge_field(self):
        if 'recaptcha_response_field' in self.cleaned_data:
            self.validate_captcha()
        return self.cleaned_data['recaptcha_challenge_field']

    def validate_captcha(self):
        rcf = self.cleaned_data['recaptcha_challenge_field']
        rrf = self.cleaned_data['recaptcha_response_field']
        ip_address = self.REQUEST.META['REMOTE_ADDR']
        check = captcha.submit(rcf, rrf, settings.RECAPTCHA_PRIVATE_KEY, ip_address)
        if not check.is_valid:
            raise ValidationError('You have not entered the correct words')
