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


class FetchEventsForMonthTests(BaseEventServiceTest):
    def setUp(self):
        super().setUp()
        
        # Create additional events for specific month testing
        # Events in January 2024
        jan_first = datetime.date(2024, 1, 1)
        jan_last = datetime.date(2024, 1, 31)
        jan_middle = datetime.date(2024, 1, 15)
        
        Event.objects.create(
            program=self.program,
            name="January First",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_first, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(jan_first, datetime.datetime.min.time())),
            visible=True,
        )
        
        Event.objects.create(
            program=self.program,
            name="January Last",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_last, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(jan_last, datetime.datetime.min.time())),
            visible=True,
        )
        
        Event.objects.create(
            program=self.program,
            name="January Middle",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            visible=True,
        )
        
        # Event in February 2024 (should not be included in January tests)
        feb_first = datetime.date(2024, 2, 1)
        Event.objects.create(
            program=self.program,
            name="February First",
            starts_at=timezone.make_aware(datetime.datetime.combine(feb_first, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(feb_first, datetime.datetime.min.time())),
            visible=True,
        )
        
        # Not visible event in January
        Event.objects.create(
            program=self.program,
            name="January Hidden",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            visible=False,
        )
        
        # Archived event in January
        Event.objects.create(
            program=self.program,
            name="January Archived",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            visible=True,
            archived=True,
        )

    def test_fetch_events_for_month_with_only_visible(self):
        # Arrange
        # (Setup is done in setUp method)
        
        # Act
        result = self.service.fetch_events_for_month(2024, 1)
        
        # Assert
        self.assertEqual(3, result.count(), "Should return only visible events for January 2024")
        event_names = [event.name for event in result]
        self.assertIn("January First", event_names)
        self.assertIn("January Last", event_names)
        self.assertIn("January Middle", event_names)
        self.assertNotIn("February First", event_names)
        self.assertNotIn("January Hidden", event_names)
        self.assertNotIn("January Archived", event_names)

    def test_fetch_events_for_month_with_all_visibility(self):
        # Arrange
        # (Setup is done in setUp method)
        
        # Act
        result = self.service.fetch_events_for_month(2024, 1, only_visible=False)
        
        # Assert
        self.assertEqual(4, result.count(), "Should return all non-archived events for January 2024 regardless of visibility")
        event_names = [event.name for event in result]
        self.assertIn("January First", event_names)
        self.assertIn("January Last", event_names)
        self.assertIn("January Middle", event_names)
        self.assertIn("January Hidden", event_names)
        self.assertNotIn("February First", event_names)
        self.assertNotIn("January Archived", event_names)

    def test_fetch_events_for_month_with_archived(self):
        # Arrange
        # (Setup is done in setUp method)
        
        # Act
        result = self.service.fetch_events_for_month(2024, 1, include_archived=True, only_visible=False)
        
        # Assert
        self.assertEqual(5, result.count(), "Should return all events for January 2024 including archived")
        event_names = [event.name for event in result]
        self.assertIn("January First", event_names)
        self.assertIn("January Last", event_names)
        self.assertIn("January Middle", event_names)
        self.assertIn("January Hidden", event_names)
        self.assertIn("January Archived", event_names)
        self.assertNotIn("February First", event_names)

    def test_fetch_events_for_month_leap_year_february(self):
        # Arrange - Create event on Feb 29, 2024 (leap year)
        feb_29 = datetime.date(2024, 2, 29)
        Event.objects.create(
            program=self.program,
            name="Leap Day Event",
            starts_at=timezone.make_aware(datetime.datetime.combine(feb_29, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(feb_29, datetime.datetime.min.time())),
            visible=True,
        )
        
        # Act
        result = self.service.fetch_events_for_month(2024, 2)
        
        # Assert
        self.assertEqual(2, result.count(), "Should include events on leap day")
        event_names = [event.name for event in result]
        self.assertIn("February First", event_names)
        self.assertIn("Leap Day Event", event_names)

    def test_fetch_events_for_month_empty_month(self):
        # Arrange
        # (No events in March 2024)
        
        # Act
        result = self.service.fetch_events_for_month(2024, 3)
        
        # Assert
        self.assertEqual(0, result.count(), "Should return no events for empty month")
