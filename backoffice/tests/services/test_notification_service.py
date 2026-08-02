from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Notification, Program, Registration
from backoffice.services.notification_service import NotificationService


class NotificationServiceTests(TestCase):

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        starts_at = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(
            name='Test Event',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            program=self.program,
            location='Test Location',
            description='Test Description',
        )
        self.registration = Registration.objects.create(
            event=self.event,
            first_name='Stale',
            last_name='Rider',
            name='Stale Rider',
            email='rider@example.com',
            ride_leader_preference=Registration.RideLeaderPreference.NO,
        )
        self.service = NotificationService()

    def test_records_a_notification_without_a_target(self):
        # Act
        notification = self.service.record(
            Notification.KIND_STAFF_UNCONFIRMED_DIGEST,
            ['staff@example.com'],
        )

        # Assert
        self.assertEqual(notification.recipients, ['staff@example.com'])
        self.assertIsNone(notification.target)
        self.assertEqual(notification.target_repr, '')

    def test_records_a_notification_with_a_target(self):
        # Act
        notification = self.service.record(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            ['rider@example.com'],
            target=self.registration,
        )

        # Assert
        self.assertEqual(notification.target, self.registration)
        self.assertEqual(notification.target_repr, f'Registration #{self.registration.pk}')

    def test_rejects_an_empty_recipient_list(self):
        # Act / Assert
        with self.assertRaises(ValidationError):
            self.service.record(Notification.KIND_STAFF_UNCONFIRMED_DIGEST, [])

    def test_rejects_a_blank_recipient(self):
        # Act / Assert
        with self.assertRaises(ValidationError):
            self.service.record(Notification.KIND_STAFF_UNCONFIRMED_DIGEST, ['  '])

    def test_reports_a_target_that_has_been_notified(self):
        # Arrange
        self.service.record(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            ['rider@example.com'],
            target=self.registration,
        )

        # Act
        sent = self.service.has_been_sent(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            self.registration,
        )

        # Assert
        self.assertTrue(sent)

    def test_does_not_confuse_kinds_for_the_same_target(self):
        # Arrange
        self.service.record(
            Notification.KIND_STAFF_UNCONFIRMED_DIGEST,
            ['staff@example.com'],
            target=self.registration,
        )

        # Act
        sent = self.service.has_been_sent(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            self.registration,
        )

        # Assert
        self.assertFalse(sent)

    def test_returns_the_subset_of_target_ids_already_notified(self):
        # Arrange
        other = Registration.objects.create(
            event=self.event,
            first_name='Other',
            last_name='Rider',
            name='Other Rider',
            email='other@example.com',
            ride_leader_preference=Registration.RideLeaderPreference.NO,
        )
        self.service.record(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            ['rider@example.com'],
            target=self.registration,
        )

        # Act
        notified = self.service.targets_already_notified(
            Notification.KIND_REGISTRATION_VERIFICATION_REMINDER,
            Registration,
            [self.registration.id, other.id],
        )

        # Assert
        self.assertEqual(notified, {self.registration.id})
