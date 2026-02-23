import hashlib
from urllib.parse import urlencode

from django import template

register = template.Library()


def get_gravatar_url(email, size=150):
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    params = urlencode({'s': str(size), 'd': 'mp'})
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"


@register.simple_tag
def profile_picture_url(user, size=150):
    if not user or not user.is_authenticated:
        return get_gravatar_url('', size)

    try:
        from allauth.socialaccount.models import SocialAccount
        strava_account = SocialAccount.objects.filter(
            user=user,
            provider='strava'
        ).first()

        if strava_account:
            extra_data = strava_account.extra_data
            profile_url = extra_data.get('profile_medium') or extra_data.get('profile')
            if profile_url:
                return profile_url
    except Exception:
        pass

    return get_gravatar_url(user.email, size)
