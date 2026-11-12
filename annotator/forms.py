from django import forms
from django.contrib.auth.validators import UnicodeUsernameValidator
from annotator.models import AccessCode

class AnnotatorEntryForm(forms.Form):
    username = forms.CharField(
        label="Username",
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        widget=forms.TextInput(attrs={'placeholder': 'Enter your username'})
    )
    access_code = forms.CharField(
        label="Access Code",
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter access code'})
    )

    def clean_access_code(self):
        """Reject access codes that are missing, invalid, or disabled."""
        code = self.cleaned_data.get('access_code')
        if not AccessCode.objects.filter(code=code, is_active=True).exists():
            raise forms.ValidationError("Invalid or inactive access code.")
        return code
