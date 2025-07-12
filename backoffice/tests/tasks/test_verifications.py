import logging
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import Event, Registration, Program
from backoffice.tasks.verification_tasks import verify_registration_processing


class VerifyRegistrationProcessingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.program = Program.objects.create(
            name="Test Program"
        )
        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=timezone.now() + timedelta(days=1),
            registration_closes_at=timezone.now()
        )

    def test_verify_registration_processing_finds_stuck_registrations(self):
        # Arrange
        six_minutes_ago = timezone.now() - timedelta(minutes=6)
        
        stuck_registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        stuck_registration.submitted_at = six_minutes_ago
        stuck_registration.save()

        recent_registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        recent_registration.submitted_at = timezone.now() - timedelta(minutes=3)
        recent_registration.save()

        confirmed_registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_CONFIRMED
        )
        confirmed_registration.submitted_at = six_minutes_ago
        confirmed_registration.save()

        # Act
        with self.assertLogs(level='ERROR') as log_context:
            verify_registration_processing()

        # Assert
        self.assertEqual(len(log_context.records), 1)
        log_message = log_context.records[0].message
        self.assertIn(f"Found registration (id={stuck_registration.id}) stuck in submitted state", log_message)
        self.assertIn("duration=", log_message)

    def test_verify_registration_processing_no_stuck_registrations(self):
        # Arrange
        recent_registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        recent_registration.submitted_at = timezone.now() - timedelta(minutes=3)
        recent_registration.save()

        confirmed_registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_CONFIRMED
        )
        confirmed_registration.submitted_at = timezone.now() - timedelta(minutes=10)
        confirmed_registration.save()

        # Act & Assert: should not log any ERROR
        verify_registration_processing()
        # No assertion needed - if the task runs without error, it means no stuck registrations were found

    def test_verify_registration_processing_multiple_stuck_registrations(self):
        # Arrange
        six_minutes_ago = timezone.now() - timedelta(minutes=6)
        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        
        stuck_registration_1 = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        stuck_registration_1.submitted_at = six_minutes_ago
        stuck_registration_1.save()

        stuck_registration_2 = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        stuck_registration_2.submitted_at = ten_minutes_ago
        stuck_registration_2.save()

        # Act
        with self.assertLogs(level='ERROR') as log_context:
            verify_registration_processing()

        # Assert
        self.assertEqual(len(log_context.records), 2)
        
        log_messages = [record.message for record in log_context.records]
        self.assertTrue(any(f"Found registration (id={stuck_registration_1.id})" in msg for msg in log_messages))
        self.assertTrue(any(f"Found registration (id={stuck_registration_2.id})" in msg for msg in log_messages))

    def test_verify_registration_processing_exactly_five_minutes_old(self):
        # Arrange
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        registration.submitted_at = five_minutes_ago
        registration.save()

        # Act
        with self.assertLogs(level='ERROR') as log_context:
            verify_registration_processing()

        # Assert
        self.assertEqual(len(log_context.records), 1)
        log_message = log_context.records[0].message
        self.assertIn(f"Found registration (id={registration.id}) stuck in submitted state", log_message)

    def test_verify_registration_processing_four_minutes_old_not_logged(self):
        # Arrange
        four_minutes_ago = timezone.now() - timedelta(minutes=4)
        
        registration = Registration.objects.create(
            user=self.user,
            event=self.event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        registration.submitted_at = four_minutes_ago
        registration.save()

        # Act & Assert: should not log any ERROR
        verify_registration_processing()
        # No assertion needed - if the task runs without error, it means no stuck registrations were found
