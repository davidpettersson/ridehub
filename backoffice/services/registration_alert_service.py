import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from backoffice.models import Registration
from backoffice.services.email_service import EmailService

logger = logging.getLogger(__name__)

UNCONFIRMED_ALERT_THRESHOLD = timedelta(hours=1)

UNCONFIRMED_STATES = [Registration.STATE_SUBMITTED, Registration.STATE_UNVERIFIED]


class RegistrationAlertService:
    def __init__(self):
        self.email_service = EmailService()

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
            },
            subject=f"{len(stale)} unconfirmed registration{'s' if len(stale) > 1 else ''}",
            recipient_list=recipients,
        )

        now = timezone.now()
        Registration.objects.filter(id__in=[r.id for r in stale]).update(unconfirmed_alert_sent_at=now)

        logger.info('Alerted %s about %s unconfirmed registrations', recipients, len(stale))
        return len(stale)

    @staticmethod
    def _stale_registrations():
        cutoff = timezone.now() - UNCONFIRMED_ALERT_THRESHOLD

        return Registration.objects.filter(
            state__in=UNCONFIRMED_STATES,
            submitted_at__lte=cutoff,
            unconfirmed_alert_sent_at__isnull=True,
        ).select_related('event').order_by('submitted_at')
