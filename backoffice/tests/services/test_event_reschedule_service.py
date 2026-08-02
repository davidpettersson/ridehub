from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program, Registration
from backoffice.services.event_service import EventService


class EventRescheduleServiceTestCase(TestCase):
    def setUp(self):
        # Arrange
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.next_week = self.now + timedelta(days=7)
        self.service = EventService()

        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.tomorrow,
            ends_at=self.tomorrow + timedelta(hours=2),
            registration_closes_at=self.now,
            state=Event.STATE_LIVE,
        )

    def _reschedule(self, **overrides):
        arguments = {
            'starts_at': self.next_week,
            'ends_at': self.next_week + timedelta(hours=2),
            'registration_closes_at': self.next_week - timedelta(hours=1),
            'reason': 'Thunderstorms',
        }
        arguments.update(overrides)
        return self.service.reschedule_event(self.event, **arguments)

    def test_reschedule_moves_the_event(self):
        # Act
        self._reschedule()

        # Assert
        self.event.refresh_from_db()
        self.assertEqual(self.event.starts_at, self.next_week)
        self.assertEqual(self.event.ends_at, self.next_week + timedelta(hours=2))
        self.assertEqual(self.event.registration_closes_at, self.next_week - timedelta(hours=1))

    def test_reschedule_records_previous_schedule(self):
        # Arrange
        original_starts_at = self.event.starts_at
        original_ends_at = self.event.ends_at

        # Act
        self._reschedule()

        # Assert
        self.event.refresh_from_db()
        self.assertEqual(self.event.previous_starts_at, original_starts_at)
        self.assertEqual(self.event.previous_ends_at, original_ends_at)
        self.assertEqual(self.event.reschedule_reason, 'Thunderstorms')
        self.assertIsNotNone(self.event.rescheduled_at)
        self.assertTrue(self.event.rescheduled)

    def test_reschedule_keeps_state_and_registrations(self):
        # Arrange
        registration = Registration.objects.create(
            event=self.event,
            name='Rider One',
            email='rider1@example.com',
            state=Registration.STATE_CONFIRMED,
        )

        # Act
        self._reschedule()

        # Assert
        self.event.refresh_from_db()
        stored_registration = Registration.objects.get(pk=registration.pk)
        self.assertEqual(self.event.state, Event.STATE_LIVE)
        self.assertEqual(stored_registration.state, Registration.STATE_CONFIRMED)

    def test_reschedule_rejects_cancelled_event(self):
        # Arrange
        self.event.cancellation_reason = 'Snow'
        self.event.cancel()
        self.event.save()

        # Act & Assert
        with self.assertRaises(ValueError):
            self._reschedule()

    def test_reschedule_rejects_archived_event(self):
        # Arrange
        self.event.archival_reason = 'Old'
        self.event.archive()
        self.event.save()

        # Act & Assert
        with self.assertRaises(ValueError):
            self._reschedule()

    def test_reschedule_rejects_registration_closing_after_start(self):
        # Act & Assert
        with self.assertRaises(ValidationError):
            self._reschedule(registration_closes_at=self.next_week + timedelta(hours=1))

    def test_reschedule_rejects_end_before_start(self):
        # Act & Assert
        with self.assertRaises(ValidationError):
            self._reschedule(ends_at=self.next_week - timedelta(hours=1))

    def test_reschedule_rejects_blank_reason(self):
        # Act & Assert
        with self.assertRaises(ValidationError):
            self._reschedule(reason='')

    def test_second_reschedule_records_the_latest_previous_schedule(self):
        # Arrange
        self._reschedule()
        first_starts_at = self.event.starts_at
        later = self.now + timedelta(days=14)

        # Act
        self._reschedule(
            starts_at=later,
            ends_at=later + timedelta(hours=2),
            registration_closes_at=later - timedelta(hours=1),
            reason='Rescheduled again',
        )

        # Assert
        self.event.refresh_from_db()
        self.assertEqual(self.event.previous_starts_at, first_starts_at)
        self.assertEqual(self.event.starts_at, later)
        self.assertEqual(self.event.reschedule_reason, 'Rescheduled again')

    def test_notify_registrants_emails_confirmed_registrations_only(self):
        # Arrange
        Registration.objects.create(
            event=self.event,
            name='Confirmed Rider',
            email='confirmed@example.com',
            state=Registration.STATE_CONFIRMED,
        )
        Registration.objects.create(
            event=self.event,
            name='Withdrawn Rider',
            email='withdrawn@example.com',
            state=Registration.STATE_WITHDRAWN,
        )
        self._reschedule()

        # Act
        notified = self.service.notify_registrants_of_reschedule(self.event, base_url='https://example.com')

        # Assert
        self.assertEqual(notified, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['confirmed@example.com'])
        self.assertIn('RIDE RESCHEDULED', mail.outbox[0].subject)

    def test_notification_email_contains_old_and_new_times_and_reason(self):
        # Arrange
        Registration.objects.create(
            event=self.event,
            name='Confirmed Rider',
            email='confirmed@example.com',
            state=Registration.STATE_CONFIRMED,
        )
        original_starts_at = self.event.starts_at
        self._reschedule()

        # Act
        self.service.notify_registrants_of_reschedule(self.event, base_url='https://example.com')

        # Assert
        body = mail.outbox[0].body
        self.assertIn(timezone.localtime(original_starts_at).strftime('%B'), body)
        self.assertIn('Thunderstorms', body)
        self.assertIn('https://example.com', body)
