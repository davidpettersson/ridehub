from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView
from sesame.utils import get_query_string

from backoffice.services import EmailService
from web.forms import EmailLoginForm


class LoginFormView(FormView):
    template_name = "web/login/login_form.html"
    form_class = EmailLoginForm

    def get_user(self, email: str) -> User | None:
        """Find the user with this email address."""
        User = get_user_model()
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def create_link(self, user: User) -> str:
        """Create a login link for this user."""
        link = reverse("login")
        link = self.request.build_absolute_uri(link)
        link += get_query_string(user)
        return link

    def send_email(self, user: User, link: str) -> None:
        """Send an email with this login link to this user."""
        context = {
            'login_link': link
        }
        
        EmailService.send_email(
            template_name='login_link',
            context=context,
            subject="Log in to our app",
            recipient_list=[user.email],
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
