from datetime import timedelta

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
