from django.conf import settings
from django.urls import reverse


def get_sesame_max_age_minutes():
    """Get the SESAME_MAX_AGE setting in minutes."""
    max_age = getattr(settings, 'SESAME_MAX_AGE', None)
    if max_age is None:
        return None
    # SESAME_MAX_AGE is in seconds, convert to minutes
    return max_age // 60


def is_sesame_one_time():
    """Check if SESAME_ONE_TIME is enabled."""
    return getattr(settings, 'SESAME_ONE_TIME', False)


def get_absolute_url(view_name, request=None):
    """Get the absolute URL for a view, using the configured WEB_HOST."""
    path = reverse(view_name)
    host = getattr(settings, 'WEB_HOST', 'obcrides.ca')
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', True) else 'http'
    
    # If we have a request object, we can be smarter about the protocol
    if request and hasattr(request, 'is_secure'):
        protocol = 'https' if request.is_secure() else 'http'
    
    return f"{protocol}://{host}{path}" 