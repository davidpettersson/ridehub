import datetime
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program
from backoffice.services.event_service import EventService


class BaseEventServiceTest(TestCase):
    def setUp(self):
        # Arrange - Common setup for all test cases
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()

        # Ensure consistent date for testing
        self.today = self.now.date()
        self.yesterday = self.today - timedelta(days=1)
        self.tomorrow = self.today + timedelta(days=1)

        # Create test events
        self._create_test_events()

        # Create service instance
        self.service = EventService()

    def _create_test_events(self):
        # Create visible events
        Event.objects.create(
            program=self.program,
            name="Yesterday",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.yesterday, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.yesterday, datetime.datetime.min.time())),
            visible=True,
        )

        Event.objects.create(
            program=self.program,
            name="Today 00:00",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.today, datetime.datetime.min.time())),
            visible=True,
        )

        Event.objects.create(
            program=self.program,
            name="Today 23:59",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(23, 59))),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(23, 59))),
            visible=True,
        )

        Event.objects.create(
            program=self.program,
            name="Tomorrow",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            visible=True,
        )

        # Create not visible events
        Event.objects.create(
            program=self.program,
            name="Today 12:00 (Not Visible)",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(12, 0))),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(12, 0))),
            visible=False,
        )

        Event.objects.create(
            program=self.program,
            name="Tomorrow (Not Visible)",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            visible=False,
        )


class FetchEventsTests(BaseEventServiceTest):
    def test_with_only_visible_events(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_events()

        # Assert
        self.assertEqual(4, result.count(), "Should return only visible events")

    def test_with_all_visibility(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_events(only_visible=False)

        # Assert
        self.assertEqual(6, result.count(), "Should return all events regardless of visibility")


class FetchUpcomingEventsTests(BaseEventServiceTest):
    def test_with_only_visible_events(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_upcoming_events(current_date=self.today)

        # Assert
        self.assertEqual(3, result.count(), "Should return only visible upcoming events")

    def test_with_all_visibility(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_upcoming_events(only_visible=False, current_date=self.today)

        # Assert
        self.assertEqual(5, result.count(), "Should return all upcoming events regardless of visibility")
