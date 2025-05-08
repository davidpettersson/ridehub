from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program


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

    def test_ends_at(self):
        ends_at = self.event.starts_at + timedelta(hours=self.event.duration)
        self.assertEqual(self.event.ends_at, ends_at)
        self.assertGreaterEqual(self.event.ends_at, self.event.starts_at)

