from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from backoffice.tasks import debug_ping


@staff_member_required
@require_POST
def trigger_task(request: HttpRequest) -> HttpResponse:
    message = request.POST.get('message', 'ping')
    result = debug_ping.delay(message)

    return JsonResponse({'task_id': result.id, 'message': message})
