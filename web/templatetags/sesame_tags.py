from django import template
from web.utils import get_sesame_max_age_minutes, is_sesame_one_time, get_absolute_url

register = template.Library()


@register.simple_tag
def sesame_max_age_minutes():
    """Get the SESAME_MAX_AGE setting in minutes."""
    return get_sesame_max_age_minutes()


@register.simple_tag
def sesame_is_one_time():
    """Check if SESAME_ONE_TIME is enabled."""
    return is_sesame_one_time()


@register.simple_tag
def absolute_url(view_name, request=None):
    """Get the absolute URL for a view."""
    return get_absolute_url(view_name, request) 