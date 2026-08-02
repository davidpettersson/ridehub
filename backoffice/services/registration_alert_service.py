import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from backoffice.models import Notification, Registration
from backoffice.services.email_service import EmailService
from backoffice.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

UNCONFIRMED_ALERT_THRESHOLD = timedelta(hours=1)

UNCONFIRMED_ALERT_EVENT_HORIZON = timedelta(hours=48)

UNCONFIRMED_STATES = [Registration.STATE_SUBMITTED, Registration.STATE_UNVERIFIED]


class RegistrationAlertService:
    def __init__(self):
        self.email_service = EmailService()
        self.notification_service = NotificationService()

    def alert_unconfirmed_registrations(self) -> int:
        recipients = settings.REGISTRATION_ALERT_EMAILS
        if not recipients:
            logger.warning('No REGISTRATION_ALERT_EMAILS configured, skipping unconfirmed registration alert')
            return 0

        stale = list(self._stale_registrations())
        if not stale:
            return 0

        self.email_service.send_email(
            template_name='unconfirmed_registrations',
            context={
                'base_url': f"https://{settings.WEB_HOST}",
                'registrations': stale,
                'threshold_hours': int(UNCONFIRMED_ALERT_THRESHOLD.total_seconds() // 3600),
                'horizon_hours': int(UNCONFIRMED_ALERT_EVENT_HORIZON.total_seconds() // 3600),
            },
            subject=f"{len(stale)} unconfirmed registration{'s' if len(stale) > 1 else ''}",
            recipient_list=recipients,
        )

        self.notification_service.record(
            kind=Notification.KIND_STAFF_UNCONFIRMED_DIGEST,
            recipients=recipients,
        )

        logger.info('Alerted %s about %s unconfirmed registrations', recipients, len(stale))
        return len(stale)

    @staticmethod
    def _stale_registrations():
        now = timezone.now()
        cutoff = now - UNCONFIRMED_ALERT_THRESHOLD

        return Registration.objects.filter(
            state__in=UNCONFIRMED_STATES,
            submitted_at__lte=cutoff,
            event__starts_at__gte=now,
            event__starts_at__lte=now + UNCONFIRMED_ALERT_EVENT_HORIZON,
        ).select_related('event').order_by('event__starts_at', 'submitted_at')
