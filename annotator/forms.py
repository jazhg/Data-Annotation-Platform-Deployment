import uuid

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from annotator.models import AccessCode, EmailAccount


class AnnotatorPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        # Only recover registered email identities, never unclaimed legacy users.
        account = EmailAccount.objects.filter(email=email.strip().lower()).first()
        if account:
            yield from (user for user in super().get_users(email.strip()) if user.pk == account.user_id)


class EmailLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        data = super().clean()
        if 'email' in data and 'password' in data:
            account = EmailAccount.objects.select_related('user').filter(email=data['email'].lower()).first()
            if account:
                self.user = authenticate(self.request, username=account.user.username, password=data['password'])
            else:
                User().set_password(data['password'])
            if self.user is None:
                raise forms.ValidationError('Invalid email or password.')
        return data


class RegistrationForm(forms.Form):
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password_confirm = forms.CharField(label='Confirm password', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    access_code = forms.CharField(max_length=50, widget=forms.PasswordInput())

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if EmailAccount.objects.filter(email=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_access_code(self):
        code = self.cleaned_data['access_code']
        if not AccessCode.objects.filter(code=code, is_active=True).exists():
            raise forms.ValidationError('Invalid or inactive access code.')
        return code

    def clean(self):
        data = super().clean()
        password = data.get('password')
        if password:
            validate_password(password, User(email=data.get('email', '')))
        if password and data.get('password_confirm') and password != data['password_confirm']:
            self.add_error('password_confirm', 'Passwords do not match.')
        return data

    @transaction.atomic
    def save(self):
        AccessCode.objects.select_for_update().get(code=self.cleaned_data['access_code'], is_active=True)
        user = User.objects.create_user(username=uuid.uuid4().hex, email=self.cleaned_data['email'], password=self.cleaned_data['password'])
        EmailAccount.objects.create(user=user, email=self.cleaned_data['email'])
        return user
