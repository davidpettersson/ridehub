import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MASK_DOT_RUN = re.compile('·+')


@register.filter(name='styled_name')
def styled_name(value):
    if not value:
        return value
    escaped = escape(value)
    styled = MASK_DOT_RUN.sub(
        lambda match: f'<span class="name-mask" aria-hidden="true">{match.group(0)}</span>',
        escaped,
    )
    return mark_safe(styled)
