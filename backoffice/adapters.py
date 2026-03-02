import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group

logger = logging.getLogger(__name__)


class RideHubSocialAccountAdapter(DefaultSocialAccountAdapter):
    def _configure_obc_user(self, user):
        staff_domain = settings.AZURE_AD_STAFF_DOMAIN
        staff_group = settings.AZURE_AD_STAFF_GROUP

        if not user.email.lower().endswith(staff_domain):
            logger.info(f"User {user.email} is not a {staff_domain} user, skipping staff configuration")
            return

        logger.info(f"Configuring {staff_domain} user {user.email} as staff")
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        try:
            group = Group.objects.get(name=staff_group)
        except Group.DoesNotExist:
            logger.error(f"Group '{staff_group}' does not exist")
            raise

        if not user.groups.filter(name=staff_group).exists():
            user.groups.add(group)
            logger.info(f"Added user {user.email} to group '{staff_group}'")
        else:
            logger.info(f"User {user.email} already in group '{staff_group}'")

    def save_user(self, request, sociallogin, form=None):
        logger.info(f"Creating new user from social login: {sociallogin.account.extra_data.get('mail', 'unknown')}")
        user = super().save_user(request, sociallogin, form)
        logger.info(f"Created user: {user.email} (id={user.id})")
        self._configure_obc_user(user)
        return user

    def pre_social_login(self, request, sociallogin):
        logger.info(f"Pre-social login for provider {sociallogin.account.provider}")
        if sociallogin.is_existing:
            user = sociallogin.user
            logger.info(f"Existing user logging in: {user.email} (id={user.id})")
            self._configure_obc_user(user)
        else:
            logger.info("New user will be created")

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        provider = sociallogin.account.provider

        if provider == 'strava':
            extra_data = sociallogin.account.extra_data
            user.first_name = extra_data.get('firstname', '')
            user.last_name = extra_data.get('lastname', '')

        email = data.get('email', '')
        user.email = email.lower() if email else ''
        logger.info(f"Populated user from {provider}: {user.email}")
        return user
