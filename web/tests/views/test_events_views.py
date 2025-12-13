from datetime import timedelta, datetime, date
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Program, Registration, Ride, SpeedRange, Route


class BaseEventViewTestCase(TestCase):
    """Base test case with common setup for event view tests."""

    def setUp(self):
        # Create users
        self.user = User.objects.create_user(
            username='regular_user',
            email='regular@example.com',
            password='password123',
            first_name='Regular'
        )

        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            is_staff=True
        )

        self.leader_user = User.objects.create_user(
            username='leader_user',
            email='leader@example.com',
            password='password123',
            first_name='Leader'
        )

        # Create program and event
        self.program = Program.objects.create(name='Test Program')

        now = timezone.now()
        self.event_starts_at = now + timedelta(days=7)
        self.registration_closes_at_time = self.event_starts_at - timedelta(days=1)

        self.event = Event.objects.create(
            program=self.program,
            name='Test Event',
            description='Test Description',
            location='Test Location',
            starts_at=self.event_starts_at,
            registration_closes_at=self.registration_closes_at_time,
            ride_leaders_wanted=True
        )

        # Create ride components
        self.route = Route.objects.create(
            name='Test Route'
        )

        self.ride = Ride.objects.create(
            name='Test Ride',
            event=self.event,
            route=self.route
        )

        self.speed_range = SpeedRange.objects.create(
            lower_limit=25,
            upper_limit=30
        )

        # Create registrations
        self.regular_registration = Registration.objects.create(
            first_name='Regular',
            last_name='User',
            name='Regular User',
            email='regular@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='123-456-7890',
            user=self.user,
            state=Registration.STATE_CONFIRMED
        )

        self.leader_registration = Registration.objects.create(
            first_name='Leader',
            last_name='User',
            name='Leader User',
            email='leader@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RideLeaderPreference.YES,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='123-456-7890',
            user=self.leader_user,
            state=Registration.STATE_CONFIRMED
        )

        self.client = Client()


class EventRegistrationsViewTests(BaseEventViewTestCase):
    """Tests for the event_registrations view."""

    def setUp(self):
        super().setUp()
        self.url = reverse('riders_list', kwargs={'event_id': self.event.id})

    def test_ride_leader_access(self):
        # Arrange
        self.client.login(username='leader_user', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations.html')
        self.assertTrue(response.context['is_ride_leader'])
        # Check that private data is visible to ride leaders
        self.assertContains(response, 'Emergency Contact')  # The actual emergency contact name
        self.assertContains(response, '123-456-7890')  # The actual emergency contact phone
        self.assertContains(response, 'mailto:regular@example.com')  # Email links

    def test_regular_user_access(self):
        # Arrange
        self.client.login(username='regular_user', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations.html')
        self.assertFalse(response.context['is_ride_leader'])
        # Check that specific private data is not exposed
        self.assertNotContains(response, 'Emergency Contact')  # The actual emergency contact name
        self.assertNotContains(response, '123-456-7890')  # The actual emergency contact phone
        self.assertNotContains(response, 'mailto:regular@example.com')  # Email links

    def test_anonymous_access(self):
        # Arrange - using a client without login
        client = Client()

        # Act
        response = client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations.html')
        self.assertFalse(response.context['is_ride_leader'])
        # Check that specific private data is not exposed
        self.assertNotContains(response, 'Emergency Contact')  # The actual emergency contact name
        self.assertNotContains(response, '123-456-7890')  # The actual emergency contact phone
        self.assertNotContains(response, 'mailto:regular@example.com')  # Email links


class EventRegistrationsFullViewTests(BaseEventViewTestCase):
    """Tests for the event_registrations_full view."""

    def setUp(self):
        super().setUp()
        self.url = reverse('event_registrations_full', kwargs={'event_id': self.event.id})

    def test_staff_access(self):
        # Arrange
        self.client.login(username='staff_user', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations_full.html')

    def test_non_staff_denied(self):
        # Arrange
        self.client.login(username='regular_user', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 403)  # Permission denied status code 


class EventDetailViewTests(BaseEventViewTestCase):
    """Tests for the event_detail view."""

    def setUp(self):
        super().setUp()
        self.url = reverse('event_detail', kwargs={'event_id': self.event.id})

        # Add multiple speed ranges to the ride
        self.speed_range_slow = SpeedRange.objects.create(
            lower_limit=20,
            upper_limit=25
        )
        self.speed_range_fast = SpeedRange.objects.create(
            lower_limit=30,
            upper_limit=35
        )

        # Add all speed ranges to the ride
        self.ride.speed_ranges.add(self.speed_range, self.speed_range_slow, self.speed_range_fast)

    def test_all_speed_ranges_displayed(self):
        # Arrange
        # We already have registrations for self.speed_range (25-30 km/h)
        # but no registrations for slow (20-25) or fast (30-35) ranges

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/detail.html')

        # Check that all speed ranges are displayed
        self.assertContains(response, '20-25 km/h')
        self.assertContains(response, '25-30 km/h')
        self.assertContains(response, '30-35 km/h')

        # Check rider counts
        self.assertContains(response, '20-25 km/h')
        self.assertContains(response, '(0 riders)')  # No riders in 20-25
        self.assertContains(response, '25-30 km/h')
        self.assertContains(response, '(1 rider + 1 leader)')  # 1 regular rider + 1 leader in 25-30
        self.assertContains(response, '30-35 km/h')
        self.assertContains(response, '(0 riders)')  # No riders in 30-35

    def test_ride_without_speed_ranges(self):
        # Arrange
        # Create a new ride without speed ranges
        ride_no_ranges = Ride.objects.create(
            name='Ride Without Speed Ranges',
            event=self.event,
            route=self.route
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ride Without Speed Ranges')
        self.assertContains(response, 'No speed ranges configured for this ride')

    def test_rider_count_display_variations(self):
        # Arrange
        # Create additional users and registrations to test different scenarios
        user3 = User.objects.create_user(username='user3', password='password123')
        user4 = User.objects.create_user(username='user4', password='password123')
        user5 = User.objects.create_user(username='user5', password='password123')
        
        # Scenario 1: All riders are leaders in speed_range_fast
        Registration.objects.create(
            name='Leader 1',
            email='leader1@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range_fast,
            ride_leader_preference=Registration.RideLeaderPreference.YES,
            emergency_contact_name='Emergency',
            emergency_contact_phone='123-456-7890',
            user=user3,
            state=Registration.STATE_CONFIRMED
        )
        Registration.objects.create(
            name='Leader 2',
            email='leader2@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range_fast,
            ride_leader_preference=Registration.RideLeaderPreference.YES,
            emergency_contact_name='Emergency',
            emergency_contact_phone='123-456-7890',
            user=user4,
            state=Registration.STATE_CONFIRMED
        )
        
        # Scenario 2: Only regular riders in speed_range_slow
        Registration.objects.create(
            name='Regular 1',
            email='regular1@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range_slow,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            emergency_contact_name='Emergency',
            emergency_contact_phone='123-456-7890',
            user=user5,
            state=Registration.STATE_CONFIRMED
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        
        # Check scenario 1: All leaders (30-35 km/h)
        self.assertContains(response, '30-35 km/h')
        self.assertContains(response, '(2 leaders)')
        
        # Check scenario 2: No leaders (20-25 km/h)
        self.assertContains(response, '20-25 km/h')
        self.assertContains(response, '(1 rider)')
        
        # Check existing scenario: Mixed (25-30 km/h)
        self.assertContains(response, '25-30 km/h')
        self.assertContains(response, '(1 rider + 1 leader)')

    def test_authenticated_user_sees_registration_status(self):
        # Arrange
        self.client.login(username='regular_user', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user_is_registered'])
        self.assertContains(response, 'You are registered for this event')

    def test_unauthenticated_user_does_not_see_registration_status(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user_is_registered'])
        self.assertNotContains(response, 'You are registered for this event')

    def test_event_detail_with_external_registration_url_and_no_registration_closes_at(self):
        now = timezone.now()
        event = Event.objects.create(
            program=self.program,
            name='External Registration Event',
            starts_at=now + timedelta(days=7),
            registration_closes_at=None,
            external_registration_url='https://example.com/register'
        )
        url = reverse('event_detail', kwargs={'event_id': event.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/detail.html')


class EventViewTimezoneTests(TestCase):
    """Tests for timezone handling in event views."""

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.client = Client()
        
    def test_calendar_view_timezone_handling(self):
        """Test that events are placed on correct calendar dates regardless of UTC vs local time."""
        # Create an event at 7 PM local time in the future
        # When converted to UTC, this becomes the next day (midnight UTC)
        # This tests that the calendar uses local dates, not UTC dates
        now = timezone.now()
        future_date = now + timedelta(days=30)

        local_datetime = datetime(future_date.year, future_date.month, future_date.day, 19, 0, tzinfo=ZoneInfo('America/Toronto'))

        event = Event.objects.create(
            program=self.program,
            name='Evening Event',
            description='Test event at 7 PM',
            starts_at=local_datetime,
            registration_closes_at=local_datetime - timedelta(days=1),
        )

        # Get calendar view for the event's month
        url = reverse('calendar_month', kwargs={'year': future_date.year, 'month': future_date.month})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # The event should appear on the correct local date in the events_by_date context
        events_by_date = response.context['events_by_date']

        # Check that the event is on the correct date (local date, not UTC date)
        event_date = date(future_date.year, future_date.month, future_date.day)
        self.assertIn(event_date, events_by_date)
        self.assertEqual(len(events_by_date[event_date]), 1)
        self.assertEqual(events_by_date[event_date][0].name, 'Evening Event')

        # Ensure it's NOT on the next day (which would be the UTC date)
        next_day = future_date + timedelta(days=1)
        wrong_date = date(next_day.year, next_day.month, next_day.day)
        if wrong_date in events_by_date:
            # If the date exists, it should not contain our evening event
            event_names = [e.name for e in events_by_date[wrong_date]]
            self.assertNotIn('Evening Event', event_names)
    
    def test_event_list_view_timezone_handling(self):
        """Test that events are grouped by correct dates in the event list view."""
        # Create two events: one in the evening of day 1, one in the morning of day 2
        # Use future dates to ensure they appear in the upcoming view
        now = timezone.now()
        future_date = now + timedelta(days=30)

        evening_datetime = datetime(future_date.year, future_date.month, future_date.day, 19, 0, tzinfo=ZoneInfo('America/Toronto'))
        next_day = future_date + timedelta(days=1)
        morning_datetime = datetime(next_day.year, next_day.month, next_day.day, 9, 0, tzinfo=ZoneInfo('America/Toronto'))

        evening_event = Event.objects.create(
            program=self.program,
            name='Evening Event',
            description='Test event at 7 PM',
            starts_at=evening_datetime,
            registration_closes_at=evening_datetime - timedelta(days=1),
        )

        morning_event = Event.objects.create(
            program=self.program,
            name='Morning Event',
            description='Test event at 9 AM',
            starts_at=morning_datetime,
            registration_closes_at=morning_datetime - timedelta(days=1),
        )

        url = reverse('upcoming')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that events are grouped by correct local dates
        events_by_date = response.context['events_by_date']

        # Should have two groups for the two different days
        self.assertEqual(len(events_by_date), 2)

        # Verify each event is in the correct date group
        date_groups = dict(events_by_date)

        evening_date = date(future_date.year, future_date.month, future_date.day)
        evening_events = date_groups[evening_date]
        self.assertEqual(len(evening_events), 1)
        self.assertEqual(evening_events[0].name, 'Evening Event')

        morning_date = date(next_day.year, next_day.month, next_day.day)
        morning_events = date_groups[morning_date]
        self.assertEqual(len(morning_events), 1)
        self.assertEqual(morning_events[0].name, 'Morning Event')


class CalendarMonthPreservationTests(TestCase):
    """Tests for preserving selected month when navigating between calendar and event details."""

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.client = Client()

        now = timezone.now()

        # Create event 30 days in the future
        first_event_date = now + timedelta(days=30)
        first_event_datetime = datetime(first_event_date.year, first_event_date.month, first_event_date.day, 10, 0, tzinfo=ZoneInfo('America/Toronto'))
        self.first_event = Event.objects.create(
            program=self.program,
            name='First Event',
            description='Event in first month',
            starts_at=first_event_datetime,
            registration_closes_at=first_event_datetime - timedelta(days=1),
        )

        # Create event 90 days in the future (different month)
        second_event_date = now + timedelta(days=90)
        second_event_datetime = datetime(second_event_date.year, second_event_date.month, second_event_date.day, 10, 0, tzinfo=ZoneInfo('America/Toronto'))
        self.second_event = Event.objects.create(
            program=self.program,
            name='Second Event',
            description='Event in second month',
            starts_at=second_event_datetime,
            registration_closes_at=second_event_datetime - timedelta(days=1),
        )

        # Store the dates for use in tests
        self.first_month = first_event_date.month
        self.first_year = first_event_date.year
        self.second_month = second_event_date.month
        self.second_year = second_event_date.year

    def test_calendar_view_stores_selected_month_in_session(self):
        # Arrange
        url = reverse('calendar_month', kwargs={'year': self.first_year, 'month': self.first_month})

        # Act
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['calendar_selected_year'], self.first_year)
        self.assertEqual(self.client.session['calendar_selected_month'], self.first_month)

    def test_events_redirect_uses_stored_month(self):
        # Arrange
        session = self.client.session
        session['preferred_events_view'] = 'calendar'
        session['calendar_selected_year'] = self.first_year
        session['calendar_selected_month'] = self.first_month
        session.save()

        # Act
        response = self.client.get(reverse('events'))

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('calendar_month', kwargs={'year': self.first_year, 'month': self.first_month}))

    def test_events_redirect_falls_back_to_calendar_without_stored_month(self):
        # Arrange
        session = self.client.session
        session['preferred_events_view'] = 'calendar'
        session.save()

        # Act
        response = self.client.get(reverse('events'))

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('calendar'))

    def test_navigation_to_event_detail_and_back_preserves_month(self):
        # Arrange
        calendar_url = reverse('calendar_month', kwargs={'year': self.first_year, 'month': self.first_month})

        # Act - View first month calendar
        calendar_response = self.client.get(calendar_url)
        self.assertEqual(calendar_response.status_code, 200)

        # Act - View event detail
        event_detail_url = reverse('event_detail', kwargs={'event_id': self.first_event.id})
        detail_response = self.client.get(event_detail_url)
        self.assertEqual(detail_response.status_code, 200)

        # Act - Navigate back to events
        back_response = self.client.get(reverse('events'))

        # Assert - Should return to first month, not current month
        self.assertEqual(back_response.status_code, 302)
        self.assertEqual(back_response.url, reverse('calendar_month', kwargs={'year': self.first_year, 'month': self.first_month}))

    def test_switching_months_updates_session(self):
        # Arrange
        first_url = reverse('calendar_month', kwargs={'year': self.first_year, 'month': self.first_month})
        second_url = reverse('calendar_month', kwargs={'year': self.second_year, 'month': self.second_month})

        # Act - View first month
        self.client.get(first_url)
        self.assertEqual(self.client.session['calendar_selected_month'], self.first_month)
        self.assertEqual(self.client.session['calendar_selected_year'], self.first_year)

        # Act - Switch to second month
        self.client.get(second_url)

        # Assert - Session should be updated
        self.assertEqual(self.client.session['calendar_selected_month'], self.second_month)
        self.assertEqual(self.client.session['calendar_selected_year'], self.second_year)

    def test_events_redirect_prefers_upcoming_when_not_calendar(self):
        # Arrange
        session = self.client.session
        session['preferred_events_view'] = 'upcoming'
        session['calendar_selected_year'] = self.first_year
        session['calendar_selected_month'] = self.first_month
        session.save()

        # Act
        response = self.client.get(reverse('events'))

        # Assert - Should redirect to upcoming, not calendar
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('upcoming'))
