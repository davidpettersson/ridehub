import datetime
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program, Registration, Ride, Route, SpeedRange
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
            state=Event.STATE_LIVE,
        )

        Event.objects.create(
            program=self.program,
            name="Today 00:00",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.today, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        Event.objects.create(
            program=self.program,
            name="Today 23:59",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(23, 59))),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(23, 59))),
            state=Event.STATE_LIVE,
        )

        Event.objects.create(
            program=self.program,
            name="Tomorrow",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        # Create not visible events
        Event.objects.create(
            program=self.program,
            name="Today 12:00 (Not Visible)",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(12, 0))),
            registration_closes_at=timezone.make_aware(datetime.datetime.combine(self.today, datetime.time(12, 0))),
            state=Event.STATE_DRAFT,
        )

        Event.objects.create(
            program=self.program,
            name="Tomorrow (Not Visible)",
            starts_at=timezone.make_aware(datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(self.tomorrow, datetime.datetime.min.time())),
            state=Event.STATE_DRAFT,
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
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(jan_first, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        Event.objects.create(
            program=self.program,
            name="January Last",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_last, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(jan_last, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        Event.objects.create(
            program=self.program,
            name="January Middle",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        # Event in February 2024 (should not be included in January tests)
        feb_first = datetime.date(2024, 2, 1)
        Event.objects.create(
            program=self.program,
            name="February First",
            starts_at=timezone.make_aware(datetime.datetime.combine(feb_first, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(feb_first, datetime.datetime.min.time())),
            state=Event.STATE_LIVE,
        )

        # Not visible event in January
        Event.objects.create(
            program=self.program,
            name="January Hidden",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            state=Event.STATE_DRAFT,
        )

        # Archived event in January
        Event.objects.create(
            program=self.program,
            name="January Archived",
            starts_at=timezone.make_aware(datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            registration_closes_at=timezone.make_aware(
                datetime.datetime.combine(jan_middle, datetime.datetime.min.time())),
            state=Event.STATE_ARCHIVED,
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
        self.assertEqual(4, result.count(),
                         "Should return all non-archived events for January 2024 regardless of visibility")
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
            state=Event.STATE_LIVE,
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


class DuplicateEventTestCase(TestCase):
    def setUp(self):
        self.service = EventService()
        self.program = Program.objects.create(name="Test Program")
        self.route1 = Route.objects.create(name="Route 1")
        self.route2 = Route.objects.create(name="Route 2")
        self.speed_range_slow = SpeedRange.objects.create(lower_limit=15, upper_limit=20)
        self.speed_range_fast = SpeedRange.objects.create(lower_limit=25, upper_limit=30)

        self.base_start_time = timezone.make_aware(
            datetime.datetime(2025, 6, 15, 9, 0, 0)
        )
        self.base_end_time = self.base_start_time + datetime.timedelta(hours=3)
        self.base_registration_close = self.base_start_time - datetime.timedelta(hours=2)

        self.source_event = Event.objects.create(
            program=self.program,
            name="Original Event",
            state=Event.STATE_LIVE,
            location="Test Location",
            location_url="https://maps.example.com/test",
            starts_at=self.base_start_time,
            ends_at=self.base_end_time,
            registration_closes_at=self.base_registration_close,
            external_registration_url="https://external.example.com",
            registration_limit=50,
            description="Original description",
            virtual=True,
            ride_leaders_wanted=True,
            requires_emergency_contact=True,
            requires_membership=True,
            organizer_email="organizer@example.com",
        )

        self.ride1 = Ride.objects.create(
            event=self.source_event,
            name="Ride A",
            description="Ride A description",
            route=self.route1,
            ordering=0,
        )
        self.ride1.speed_ranges.add(self.speed_range_slow)

        self.ride2 = Ride.objects.create(
            event=self.source_event,
            name="Ride B",
            description="Ride B description",
            route=self.route2,
            ordering=1,
        )
        self.ride2.speed_ranges.add(self.speed_range_slow, self.speed_range_fast)

    def test_duplicate_event_copies_basic_fields(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event Name", new_date
        )

        self.assertEqual(new_event.name, "New Event Name")
        self.assertEqual(new_event.program, self.program)
        self.assertEqual(new_event.location, "Test Location")
        self.assertEqual(new_event.location_url, "https://maps.example.com/test")
        self.assertEqual(new_event.external_registration_url, "https://external.example.com")
        self.assertEqual(new_event.registration_limit, 50)
        self.assertEqual(new_event.description, "Original description")
        self.assertEqual(new_event.virtual, True)
        self.assertEqual(new_event.ride_leaders_wanted, True)
        self.assertEqual(new_event.requires_emergency_contact, True)
        self.assertEqual(new_event.requires_membership, True)
        self.assertEqual(new_event.organizer_email, "organizer@example.com")

    def test_duplicate_event_sets_visible_true(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertTrue(new_event.visible)

    def test_duplicate_event_clears_cancelled_status(self):
        self.source_event.cancel()
        self.source_event.cancellation_reason = "Bad weather"
        self.source_event.save()

        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertFalse(new_event.cancelled)
        self.assertIsNone(new_event.cancelled_at)
        self.assertEqual(new_event.cancellation_reason, "")

    def test_duplicate_event_does_not_copy_archived_fields(self):
        self.source_event.archive()
        self.source_event.save()

        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertFalse(new_event.archived)
        self.assertIsNone(new_event.archived_at)

    def test_duplicate_event_inherits_same_times(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertEqual(new_event.starts_at.time(), self.source_event.starts_at.time())
        self.assertEqual(new_event.ends_at.time(), self.source_event.ends_at.time())
        self.assertEqual(new_event.starts_at.date(), new_date)
        self.assertEqual(new_event.ends_at.date(), new_date)

    def test_duplicate_event_preserves_multi_day_span(self):
        self.source_event.ends_at = self.source_event.starts_at + datetime.timedelta(days=2, hours=3)
        self.source_event.save()

        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        original_duration = self.source_event.ends_at - self.source_event.starts_at
        new_duration = new_event.ends_at - new_event.starts_at
        self.assertEqual(new_duration, original_duration)
        self.assertEqual(new_event.ends_at.date(), new_date + datetime.timedelta(days=2))

    def test_duplicate_event_inherits_registration_closes_at_time(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertEqual(
            new_event.registration_closes_at.time(),
            self.source_event.registration_closes_at.time()
        )
        expected_reg_close_date = self.source_event.registration_closes_at.date() + datetime.timedelta(days=7)
        self.assertEqual(new_event.registration_closes_at.date(), expected_reg_close_date)

    def test_duplicate_event_handles_null_ends_at(self):
        self.source_event.ends_at = None
        self.source_event.save()

        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertIsNone(new_event.ends_at)

    def test_duplicate_event_creates_new_event_object(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertNotEqual(new_event.pk, self.source_event.pk)
        self.assertEqual(Event.objects.count(), 2)

    def test_duplicate_event_deep_copies_rides(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertEqual(new_event.ride_set.count(), 2)
        self.assertEqual(Ride.objects.count(), 4)

        new_rides = list(new_event.ride_set.all())
        original_ride_pks = [self.ride1.pk, self.ride2.pk]
        for new_ride in new_rides:
            self.assertNotIn(new_ride.pk, original_ride_pks)

    def test_duplicate_event_copies_ride_fields(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        new_rides = list(new_event.ride_set.order_by('ordering'))
        self.assertEqual(new_rides[0].name, "Ride A")
        self.assertEqual(new_rides[0].description, "Ride A description")
        self.assertEqual(new_rides[0].ordering, 0)
        self.assertEqual(new_rides[1].name, "Ride B")
        self.assertEqual(new_rides[1].description, "Ride B description")
        self.assertEqual(new_rides[1].ordering, 1)

    def test_duplicate_event_rides_reference_same_routes(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        new_rides = list(new_event.ride_set.order_by('ordering'))
        self.assertEqual(new_rides[0].route, self.route1)
        self.assertEqual(new_rides[1].route, self.route2)
        self.assertEqual(Route.objects.count(), 2)

    def test_duplicate_event_rides_have_same_speed_range_associations(self):
        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        new_rides = list(new_event.ride_set.order_by('ordering'))

        self.assertEqual(list(new_rides[0].speed_ranges.all()), [self.speed_range_slow])
        self.assertEqual(
            set(new_rides[1].speed_ranges.all()),
            {self.speed_range_slow, self.speed_range_fast}
        )
        self.assertEqual(SpeedRange.objects.count(), 2)

    def test_duplicate_event_does_not_copy_registrations(self):
        user = User.objects.create_user(username="testuser", email="test@example.com")
        Registration.objects.create(
            event=self.source_event,
            name="Test User",
            email="test@example.com",
            user=user,
        )

        new_date = self.base_start_time.date() + datetime.timedelta(days=7)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertEqual(self.source_event.registration_set.count(), 1)
        self.assertEqual(new_event.registration_set.count(), 0)

    def test_duplicate_event_accepts_date_object(self):
        new_date = datetime.date(2025, 7, 1)

        new_event = self.service.duplicate_event(
            self.source_event, "New Event", new_date
        )

        self.assertEqual(new_event.starts_at.date(), new_date)
