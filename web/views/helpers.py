import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest

from backoffice.models import Registration

logger = logging.getLogger(__name__)


@login_required
def populate_first_last_names(request: HttpRequest) -> HttpResponse:
    k = 0

    for r in Registration.objects.all():
        if r.first_name or r.last_name:
            logger.warning(f"{r.id} already has first or last name")
            continue

        old_first = r.first_name
        old_last = r.last_name

        r.first_name = r.user.first_name
        r.last_name = r.user.last_name
        r.save()
        k += 1

        logger.info(f"Updating r.id={r.id}: ({old_first}, {old_last}) => ({r.first_name}, {r.last_name})")

    return HttpResponse(f"Updated {k} records")


