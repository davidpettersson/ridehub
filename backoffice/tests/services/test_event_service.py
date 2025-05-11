from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program
from backoffice.services.event_service import EventService


class EventServiceTests(TestCase):
    def setUp(self):
        program = Program.objects.create(name="Test Program")
        self.now = timezone.now()

        # Creating four events
        #  - Yesterday
        #  - Today 00:00
        #  - Today 23:59
        #  - Tomorrow

        Event.objects.create(
            program=program,
            name="Yesterday",
            starts_at=self.now - timedelta(days=-1),
            registration_closes_at=self.now - timedelta(days=-1),
        )

        Event.objects.create(
            program=program,
            name="Today 00:00",
            starts_at=self.now.replace(hour=0, minute=0),
            registration_closes_at=self.now.replace(hour=0, minute=0),
        )

        Event.objects.create(
            program=program,
            name="Today 23:59",
            starts_at=self.now.replace(hour=23, minute=59),
            registration_closes_at=self.now.replace(hour=23, minute=59),
        )

        Event.objects.create(
            program=program,
            name="Tomorrow",
            starts_at=self.now + timedelta(days=1),
            registration_closes_at=self.now + timedelta(days=1),
        )

    def test_fetch_events(self):
        es = EventService()
        self.assertEqual(4, es.fetch_events().count())

    def test_upcoming_doesnt_contain_yesterday(self):
        es = EventService()
        self.assertEqual(3, es.fetch_upcoming_events().count())
