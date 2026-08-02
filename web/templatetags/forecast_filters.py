from django import template

from backoffice.services.event_service import EventService
from backoffice.services.forecast_summary import summarize

register = template.Library()


@register.inclusion_tag('web/events/_forecast_badge_slot.html')
def forecast_badge(event, compact=False):
    return {
        'event': event,
        'forecast': EventService().fetch_forecast(event),
        'compact': compact,
    }


@register.filter
def forecast_summary(forecast):
    if not forecast:
        return None
    return summarize(forecast)
