from django import template

from backoffice.services.forecast_summary import summarize

register = template.Library()


@register.filter
def forecast_summary(forecast):
    if not forecast:
        return None
    return summarize(forecast)
