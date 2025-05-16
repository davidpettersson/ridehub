from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

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
        
        self.event = Event.objects.create(
            program=self.program,
            name='Test Event',
            description='Test Description',
            location='Test Location',
            starts_at='2023-01-01T10:00:00Z',
            registration_closes_at='2022-12-31T23:59:59Z',
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
            name='Regular User',
            email='regular@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RIDE_LEADER_NO,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='123-456-7890',
            user=self.user,
            state=Registration.STATE_CONFIRMED
        )
        
        self.leader_registration = Registration.objects.create(
            name='Leader User',
            email='leader@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RIDE_LEADER_YES,
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
        self.assertContains(response, '123-456-7890')       # The actual emergency contact phone
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
        self.assertNotContains(response, '123-456-7890')       # The actual emergency contact phone
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
        self.assertNotContains(response, '123-456-7890')       # The actual emergency contact phone
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