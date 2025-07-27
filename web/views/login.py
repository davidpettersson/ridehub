import logging

from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import FormView
from sesame.utils import get_query_string
from sesame.views import LoginView as SesameLoginView

from backoffice.services.email_service import EmailService
from web.forms import EmailLoginForm
from backoffice.utils import lower_email
from web.utils import get_sesame_max_age_minutes, is_sesame_one_time, get_absolute_url

logger = logging.getLogger(__name__)


class LoginFormView(FormView):
    template_name = "web/login/login_form.html"
    form_class = EmailLoginForm

    def _get_user(self, email: str) -> User | None:
        User = get_user_model()
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def _create_link(self, user: User) -> str:
        link = reverse("login")
        link = self.request.build_absolute_uri(link)
        link += get_query_string(user)
        return link

    def _send_email(self, user: User, link: str) -> None:
        # Build base URL from the request
        base_url = self.request.build_absolute_uri('/').rstrip('/')
        
        context = {
            'login_link': link,
            'base_url': base_url,
        }

        EmailService().send_email(
            template_name='login_link',
            context=context,
            subject="Login link",
            recipient_list=[user.email],
        )

    def _email_submitted(self, email: str) -> None:
        user = self._get_user(email)
        if user is None:
            # Ignore the case when no user is registered with this address.
            # Possible improvement: send an email telling them to register.
            logger.warning("User not found: %s", email)
            return
        link = self._create_link(user)
        self._send_email(user, link)

    def form_valid(self, form):
        lowercase_email = lower_email(form.cleaned_data['email'])
        self._email_submitted(lowercase_email)
        return render(self.request, "web/login/login_email_sent.html")


class CustomLoginView(SesameLoginView):
    """Custom login view that handles expired/invalid tokens gracefully."""
    
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            # If we get any error (including 403 from invalid/expired token),
            # show a friendly error page
            logger.info(f"Login failed with sesame token: {e}")
            return render(request, "web/login/login_expired.html")


def logout_view(request):
    logout(request)
    return redirect('events')
