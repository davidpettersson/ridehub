from datetime import datetime, timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Notification, Program, Registration
from backoffice.services.registration_reminder_service import (
    RegistrationReminderService,
    reminder_moment,
)


class RegistrationReminderServiceTestCase(TestCase):

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.service = RegistrationReminderService()

    def _local(self, year, month, day, hour, minute=0):
        return timezone.make_aware(
            datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )

    def _create_event(self, starts_at, name='Test Event', state=Event.STATE_LIVE):
        event = Event.objects.create(
            name=name,
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            program=self.program,
            location='Test Location',
            description='Test Description',
        )
        Event.objects.filter(id=event.id).update(state=state)
        return Event.objects.get(id=event.id)

    def _create_registration(self, event, submitted_at, state=Registration.STATE_UNVERIFIED,
                             name='Stale Rider', email='rider@example.com'):
        registration = Registration.objects.create(
            event=event,
            first_name=name.split()[0],
            last_name=name.split()[1],
            name=name,
            email=email,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
        )
        Registration.objects.filter(id=registration.id).update(
            state=state,
            submitted_at=submitted_at,
        )
        return Registration.objects.get(id=registration.id)


class ReminderMomentTests(RegistrationReminderServiceTestCase):

    def test_evening_event_is_reminded_the_morning_of(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(moment, self._local(2026, 6, 10, 6))

    def test_early_morning_event_is_reminded_the_evening_before(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 8))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(moment, self._local(2026, 6, 9, 18))

    def test_event_exactly_four_hours_after_the_morning_slot_uses_the_morning(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 10))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(moment, self._local(2026, 6, 10, 6))

    def test_event_just_before_the_lead_threshold_falls_back_to_the_evening(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 9, 59))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(moment, self._local(2026, 6, 9, 18))

    def test_event_before_the_morning_slot_falls_back_to_the_evening(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 5))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(moment, self._local(2026, 6, 9, 18))

    def test_event_the_day_after_a_spring_forward_still_resolves_to_local_six(self):
        # Arrange
        event = self._create_event(self._local(2026, 3, 8, 18))

        # Act
        moment = reminder_moment(event)

        # Assert
        self.assertEqual(timezone.localtime(moment).hour, 6)


class RemindUnconfirmedRegistrationsTests(RegistrationReminderServiceTestCase):

    def test_reminds_an_unverified_registration_once_the_morning_slot_has_passed(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        registration = self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [registration.email])
        self.assertIn('/registrations/verify?token=', mail.outbox[0].body)

    def test_does_not_remind_before_the_morning_slot(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 5))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_reminds_an_early_morning_event_the_evening_before(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 8))
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 9, 18))

        # Assert
        self.assertEqual(reminded, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_ignores_a_registration_younger_than_six_hours(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 10, 3))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_a_registration_submitted_after_the_reminder_moment(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 8))
        self._create_registration(event, self._local(2026, 6, 9, 21))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 4))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_sends_only_one_reminder_per_registration(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12))
        self._run_at(self._local(2026, 6, 10, 6))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 7))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_records_a_notification_for_the_registration(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        registration = self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        notification = Notification.objects.get()
        self.assertEqual(notification.kind, Notification.KIND_REGISTRATION_VERIFICATION_REMINDER)
        self.assertEqual(notification.recipients, [registration.email])
        self.assertEqual(notification.target, registration)

    def test_ignores_confirmed_registrations(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12),
                                  state=Registration.STATE_CONFIRMED)

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_withdrawn_registrations(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12),
                                  state=Registration.STATE_WITHDRAWN)

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_submitted_registrations(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12),
                                  state=Registration.STATE_SUBMITTED)

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_registrations_for_events_that_already_started(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 19))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_registrations_for_cancelled_events(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18), state=Event.STATE_CANCELLED)
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_registrations_for_archived_events(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18), state=Event.STATE_ARCHIVED)
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_reminds_every_unverified_registration_that_is_due(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12),
                                  name='First Rider', email='first@example.com')
        self._create_registration(event, self._local(2026, 6, 8, 13),
                                  name='Second Rider', email='second@example.com')

        # Act
        reminded = self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(reminded, 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            ['first@example.com', 'second@example.com'],
        )

    def test_names_the_event_in_the_subject(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18), name='Sunday Ramble')
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertEqual(mail.outbox[0].subject, '[OBC] You are not registered yet for Sunday Ramble')

    def test_logs_how_many_reminders_were_sent(self):
        # Arrange
        event = self._create_event(self._local(2026, 6, 10, 18))
        self._create_registration(event, self._local(2026, 6, 8, 12))

        # Act
        with self.assertLogs('backoffice.services.registration_reminder_service', level='INFO') as logs:
            self._run_at(self._local(2026, 6, 10, 6))

        # Assert
        self.assertIn('Sent 1 unconfirmed registration reminders', logs.output[0])

    def _run_at(self, now):
        with patch('backoffice.services.registration_reminder_service.timezone.now', return_value=now):
            return self.service.remind_unconfirmed_registrations()
