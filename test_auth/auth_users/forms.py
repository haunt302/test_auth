from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm as DjangoAuthenticationForm,
    UserChangeForm as DjangoUserChangeForm,
    UserCreationForm as DjangoUserCreationForm,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from auth_users.utils import send_email_for_verify


User = get_user_model()


class AuthenticationForm(DjangoAuthenticationForm):
    def confirm_login_allowed(self, user):
        if not user.email_verify:
            send_email_for_verify(self.request, user)
            raise ValidationError(
                'email not verify check your email',
                code='invalid_login'
            )
        super().confirm_login_allowed(user)

class UserCreationForm(DjangoUserCreationForm):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'})
    )

    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        normalized_email = email.lower()
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise ValidationError(
                _("A user with that email already exists."),
                code="unique",
            )
        return email


class ProfileUpdateForm(DjangoUserChangeForm):
    password = None

    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username")


class AccountDeactivateForm(forms.Form):
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError(_("Incorrect password."))
        return password
