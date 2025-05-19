from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from backoffice.models import Event, Program, Registration


class EventModelTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")

        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.yesterday = self.now - timedelta(days=1)

        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.tomorrow,
            ends_at=self.tomorrow + timedelta(hours=2),  # Explicitly set ends_at
            registration_closes_at=self.now
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )

    def test_capacity_remaining_with_no_limit(self):
        self.assertIsNone(self.event.capacity_remaining)
        self.assertTrue(self.event.has_capacity_available)
    
    def test_capacity_remaining_with_limit(self):
        self.event.registration_limit = 10
        self.event.save()
        self.assertEqual(self.event.capacity_remaining, 10)
        self.assertTrue(self.event.has_capacity_available)
    
    def test_capacity_remaining_when_limit_reached(self):
        self.event.registration_limit = 5
        self.event.save()
        
        self.assertEqual(self.event.capacity_remaining, 5)
        self.assertTrue(self.event.has_capacity_available)

        registration = Registration.objects.create(
            name=f"Test User",
            email=f"test@example.com",
            event=self.event,
            user=self.user
        )
        registration.confirm()
        registration.save()

        self.assertEqual(self.event.registration_count, 1)
        self.assertEqual(self.event.capacity_remaining, 4)
        self.assertTrue(self.event.has_capacity_available)


class EventTimeFieldsTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.one_hour_later = self.now + timedelta(hours=1)
        self.two_hours_later = self.now + timedelta(hours=2)
        self.three_hours_later = self.now + timedelta(hours=3)

    def test_duration_with_ends_at_set(self):
        event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.now,
            ends_at=self.two_hours_later,
            registration_closes_at=self.now
        )
        
        expected_duration = timedelta(hours=2)
        self.assertEqual(event.duration, expected_duration)

    def test_duration_with_ends_at_not_set(self):
        event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.now,
            registration_closes_at=self.now
        )
        
        expected_duration = timedelta(hours=1)  # Default duration
        self.assertEqual(event.duration, expected_duration)

    def test_ends_at_calculation(self):
        event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.now,
            ends_at=self.three_hours_later,
            registration_closes_at=self.now
        )
        
        self.assertEqual(event.ends_at, self.three_hours_later)
        self.assertEqual(event.duration, timedelta(hours=3))

    def test_update_starts_at_affects_duration(self):
        event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.now,
            ends_at=self.two_hours_later,
            registration_closes_at=self.now
        )
        
        initial_duration = event.duration
        self.assertEqual(initial_duration, timedelta(hours=2))
        
        # Update starts_at to a later time
        event.starts_at = self.one_hour_later
        event.save()
        
        # Duration should now be shorter
        new_duration = event.duration
        self.assertEqual(new_duration, timedelta(hours=1))
        
    def test_update_ends_at_affects_duration(self):
        event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.now,
            ends_at=self.two_hours_later,
            registration_closes_at=self.now
        )
        
        initial_duration = event.duration
        self.assertEqual(initial_duration, timedelta(hours=2))
        
        # Update ends_at to a later time
        event.ends_at = self.three_hours_later
        event.save()
        
        # Duration should now be longer
        new_duration = event.duration
        self.assertEqual(new_duration, timedelta(hours=3))

