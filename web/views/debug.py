import logging

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from backoffice.models import Forecast
from backoffice.tasks import debug_ping, refresh_forecasts

logger = logging.getLogger(__name__)

MESSAGE_MAX_LENGTH = 200
RECENT_FORECAST_COUNT = 25

superuser_required = user_passes_test(lambda user: user.is_active and user.is_superuser)


@superuser_required
def debug_index(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/debug/index.html')


@superuser_required
def tasks_ping(request: HttpRequest) -> HttpResponse:
    context = {'message': 'ping'}

    if request.method == 'POST':
        message = (request.POST.get('message') or 'ping').strip()[:MESSAGE_MAX_LENGTH] or 'ping'
        context['message'] = message

        try:
            result = debug_ping.delay(message)
            context['result'] = {'task_id': result.id, 'message': message}
        except Exception as e:
            logger.exception('Could not queue debug_ping')
            context['error'] = f'{type(e).__name__}: {e}'

    return render(request, 'web/debug/tasks_ping.html', context)


@superuser_required
def forecasts(request: HttpRequest) -> HttpResponse:
    context = {}

    if request.method == 'POST':
        try:
            result = refresh_forecasts.delay()
            context['result'] = {'task_id': result.id}
        except Exception as e:
            logger.exception('Could not queue refresh_forecasts')
            context['error'] = f'{type(e).__name__}: {e}'

    context['forecasts'] = Forecast.objects.order_by('-prepared_at')[:RECENT_FORECAST_COUNT]

    return render(request, 'web/debug/forecasts.html', context)
