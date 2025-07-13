from django.http import HttpRequest, HttpResponse

from backoffice.tasks import perform_task_in_job


def trigger_error(request: HttpRequest) -> HttpResponse:
    return 1 / 0


def trigger_task(request: HttpRequest) -> HttpResponse:
    print('TRIGGER_TASK')
    perform_task_in_job.delay()
    return HttpResponse('OK')
