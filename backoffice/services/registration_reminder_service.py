import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from backoffice.models import Event, Notification, Registration
from backoffice.services.email_service import EmailService
from backoffice.services.notification_service import NotificationService
from backoffice.services.registration_service import RegistrationService

logger = logging.getLogger(__name__)

REMINDER_MINIMUM_AGE = timedelta(hours=6)

REMINDER_MORNING_HOUR = 6

REMINDER_EVENING_HOUR = 18

REMINDER_MINIMUM_LEAD = timedelta(hours=4)

REMINDER_EVENT_HORIZON = timedelta(hours=48)


def reminder_moment(event: Event) -> datetime:
    local_start = timezone.localtime(event.starts_at)
    morning = local_start.replace(
        hour=REMINDER_MORNING_HOUR, minute=0, second=0, microsecond=0
    )

    if local_start - morning >= REMINDER_MINIMUM_LEAD:
        return morning

    previous_day = local_start.date() - timedelta(days=1)
    return timezone.make_aware(
        datetime.combine(
            previous_day,
            datetime.min.time().replace(hour=REMINDER_EVENING_HOUR),
        ),
        timezone.get_current_timezone(),
    )


class RegistrationReminderService:
    def __init__(self):
        self.email_service = EmailService()
        self.notification_service = NotificationService()
        self.registration_service = RegistrationService()

    def remind_unconfirmed_registrations(self) -> int:
        due = self._due_registrations()

        for registration in due:
            self._send_reminder(registration)

        if due:
            logger.info('Sent %s unconfirmed registration reminders', len(due))

        return len(due)

    def _due_registrations(self) -> list[Registration]:
        now = timezone.now()

        candidates = Registration.objects.filter(
            state=Registration.STATE_UNVERIFIED,
            submitted_at__lte=now - REMINDER_MINIMUM_AGE,
            event__starts_at__gte=now,
            event__starts_at__lte=now + REMINDER_EVENT_HORIZON,
        ).exclude(
            event__state__in=[Event.STATE_CANCELLED, Event.STATE_ARCHIVED],
        ).select_related('event').order_by('event__starts_at', 'submitted_at')

        candidates = [
            registration for registration in candidates
            if self._is_due(registration, now)
        ]

        if not candidates:
            return []

        already_notified = self.notification_service.targets_already_notified(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            Registration,
            [registration.id for registration in candidates],
        )

        return [
            registration for registration in candidates
            if registration.id not in already_notified
        ]

    @staticmethod
    def _is_due(registration: Registration, now: datetime) -> bool:
        moment = reminder_moment(registration.event)
        return moment <= now and registration.submitted_at <= moment

    def _send_reminder(self, registration: Registration) -> None:
        context = {
            'base_url': f"https://{settings.WEB_HOST}",
            'registration': registration,
            'verification_url': self.registration_service.build_verification_url(registration),
        }

        self.email_service.send_email(
            template_name='verification_reminder',
            context=context,
            subject=f"You are not registered yet for {registration.event.name}",
            recipient_list=[registration.email],
        )

        self.notification_service.record(
            kind=Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            recipients=[registration.email],
            target=registration,
        )
