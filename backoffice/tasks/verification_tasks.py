import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from backoffice.models import Registration

logger = logging.getLogger(__name__)


@shared_task
def verify_registration_processing():
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    unprocessed = Registration.objects.filter(
        state=Registration.STATE_SUBMITTED,
        submitted_at__lte=five_minutes_ago
    )
    for u in unprocessed:
        duration = timezone.now() - u.submitted_at
        logger.error(f"Found registration (id={u.id}) stuck in submitted state (duration={duration})")
