import new

from django import forms

from registration.forms import RegistrationFormUniqueEmail
from notification.models import NoticeType

W_TEXT = lambda s=40: forms.TextInput(attrs={'size':str(s)})

class RegistrationForm(RegistrationFormUniqueEmail):
    BLOCKED_USERNAMES = ['notemonk', 'adminmonk', 'support', 'contact',
            'register', 'administrator', 'registrar', 'superuser', 'webmaster',
            'anonymous', 'anonymoususer']

    referrer = forms.CharField(max_length=50, required=False)

    def clean_username(self):
        username = RegistrationFormUniqueEmail.clean_username(self)

        if not 6 < len(username) < 30:
            raise forms.ValidationError('Sorry, your username must be between 6 and 30 characters long')

        if username in self.BLOCKED_USERNAMES:
            raise forms.ValidationError('A user with that username already exists.')

        return username

class LoginForm(forms.Form):
    username = forms.CharField(max_length=50)
    password = forms.CharField(max_length=50, widget=forms.PasswordInput)
    persistent = forms.BooleanField(required=False, label='Stay signed in')

class UserProfileForm(forms.Form):
    first_name = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    last_name = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    email = forms.EmailField(widget=W_TEXT(30))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'size':'30'}),
                    required=False, label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'size':'30'}),
                    required=False, label='Password (re-enter)')
    institution = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    city = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    state = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    country = forms.CharField(max_length=50, required=False, widget=W_TEXT(30))
    mailing_address = forms.CharField(max_length=1024, widget=forms.Textarea, required=False)
    dob = forms.DateField(required=False, label='Birth date',
        help_text="eg: '10/25/06', '10/25/2006', '2006-10-25' ",
        widget=W_TEXT(30))
    sex = forms.ChoiceField(required=False)
    sex.choices = [('M', 'Male'), ('F', 'Female')]
    image = forms.ImageField(required=False)

    def clean(self):
        cleaned_data = self.cleaned_data
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1:
            if password1 != password2:
                del cleaned_data['password1']
                del cleaned_data['password2']
                raise forms.ValidationError('passwords do not match')

        return cleaned_data

class FeedbackForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    feedback = forms.CharField(max_length=2048, widget=forms.Textarea)

class EmailForm(forms.Form):
    email = forms.EmailField(widget=W_TEXT())
    re_enter_email = forms.EmailField(label='Re-enter Email',
                        widget=W_TEXT())

class InviteForm(forms.Form):
    emails = forms.CharField(max_length=2048, widget=forms.Textarea,
                             help_text="Separate emails by ;")
    message = forms.CharField(max_length=1024, widget=forms.Textarea,
                              required=False)

class DynForm(forms.Form):    
    
    def set_fields(self, fields):
        for k, f in fields:
            self.fields[k] = f

def make_notifications_form(data):
    klass = new.classobj('NotificationsForm', (DynForm,), {})
    obj = klass()

    for n in NoticeType.objects.all():
        if n.label.startswith('_'):
            continue
        
        field = forms.BooleanField(label = n.display,
            required=False, initial=data.get(n.label, False))

        obj.fields[n.label] = field

    return obj

class AddBookForm(forms.Form):
    title = forms.CharField(max_length=255, widget=W_TEXT())
    isbn = forms.CharField(max_length=32, required=False, widget=W_TEXT())

    tags = forms.CharField(max_length=1024,
                widget=forms.TextInput(
                    attrs={'style': 'display: none'}))

    def clean_tags(self):
        tags = self.cleaned_data['tags']
        tags = [int(t.strip()) for t in tags.split(',') if t.strip()]
        tags = list(set(tags))
        return tags

class EditBookForm(forms.Form):
    title = forms.CharField(max_length=255)
    isbn = forms.CharField(max_length=30, required=False)
    image = forms.ImageField(required=False)

    tags = forms.CharField(max_length=1024,
                widget=forms.TextInput(
                    attrs={'style': 'display: none'}))

    moderators = forms.CharField(max_length=1024, required=False,
                widget=forms.TextInput(
                    attrs={'style': 'display: none'}))

    def clean_tags(self):
        tags = self.cleaned_data['tags']
        tags = [int(t.strip()) for t in tags.split(',') if t.strip()]
        tags = list(set(tags))
        return tags
    
    def clean_moderators(self):
        moderators = self.cleaned_data['moderators']
        moderators = [int(m.strip()) for m in moderators.split(',') if m.strip()]
        moderators = list(set(moderators))
        return moderators

class MailingAddressForm(forms.Form):
    mailing_address = forms.CharField(max_length=1024, widget=forms.Textarea, required=True)
