from django.http import HttpRequest
from waffle import flag_is_active

from backoffice.models import Event
from backoffice.services.event_service import EventService
from backoffice.services.forecast_service import ForecastState


def resolve_forecast_state(request: HttpRequest, event: Event) -> ForecastState:
    if not flag_is_active(request, 'weather_forecast_badges'):
        return ForecastState.unavailable()
    return EventService().resolve_forecast(event)
