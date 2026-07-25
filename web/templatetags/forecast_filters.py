from django import template

from backoffice.services.forecast_summary import summarize
from web.forecast import resolve_forecast_state

register = template.Library()


@register.inclusion_tag('web/events/_forecast_badge_slot.html', takes_context=True)
def forecast_badge(context, event, compact=False):
    return {
        'event': event,
        'state': resolve_forecast_state(context['request'], event),
        'compact': compact,
    }


@register.filter
def forecast_summary(forecast):
    if not forecast:
        return None
    return summarize(forecast)
