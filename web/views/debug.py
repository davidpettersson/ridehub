import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from backoffice.tasks import debug_ping

logger = logging.getLogger(__name__)

MESSAGE_MAX_LENGTH = 200


@staff_member_required
def trigger_task(request: HttpRequest) -> HttpResponse:
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

    return render(request, 'web/debug/trigger_task.html', context)
