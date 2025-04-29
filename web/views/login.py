from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView
from sesame.utils import get_query_string

from web.forms import EmailLoginForm


class LoginFormView(FormView):
    template_name = "web/login/login_form.html"
    form_class = EmailLoginForm

    def get_user(self, email: str) -> object | None:
        """Find the user with this email address."""
        User = get_user_model()
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def create_link(self, user: object) -> str:
        """Create a login link for this user."""
        link = reverse("login")
        link = self.request.build_absolute_uri(link)
        link += get_query_string(user)
        return link

    def send_email(self, user: str, link: str) -> None:
        """Send an email with this login link to this user."""
        user.email_user(
            subject="[django-sesame] Log in to our app",
            message=f"""\
    Hello,

    You requested that we send you a link to log in to our app:

        {link}

    Thank you for using django-sesame!
    """,
        )

    def email_submitted(self, email: str) -> None:
        user = self.get_user(email)
        if user is None:
            # Ignore the case when no user is registered with this address.
            # Possible improvement: send an email telling them to register.
            print("user not found:", email)
            return
        link = self.create_link(user)
        self.send_email(user, link)

    def form_valid(self, form):
        self.email_submitted(form.cleaned_data["email"])
        return render(self.request, "web/login/login_email_sent.html")
