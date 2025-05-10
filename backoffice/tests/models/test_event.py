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
            registration_closes_at=self.now,
            duration=5
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )

    def test_ends_at(self):
        ends_at = self.event.starts_at + timedelta(hours=self.event.duration)
        self.assertEqual(self.event.ends_at, ends_at)
        self.assertGreaterEqual(self.event.ends_at, self.event.starts_at)

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

        Registration.objects.create(
            name=f"Test User",
            email=f"test@example.com",
            event=self.event,
            user=self.user
        )
        
        self.assertEqual(self.event.registration_count, 1)
        self.assertEqual(self.event.capacity_remaining, 4)
        self.assertTrue(self.event.has_capacity_available)

