from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from backoffice.models import Event, Program


class EventViewsTests(TestCase):

    def setUp(self):
        # Create a regular user
        self.user = User.objects.create_user(
            username='regular_user',
            email='regular@example.com',
            password='password123',
            first_name='Regular'
        )
        
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            is_staff=True
        )
        
        # Create a program for the event
        self.program = Program.objects.create(name='Test Program')
        
        # Create a test event
        self.event = Event.objects.create(
            program=self.program,
            name='Test Event',
            description='Test Description',
            location='Test Location',
            starts_at='2023-01-01T10:00:00Z',
            registration_closes_at='2022-12-31T23:59:59Z'
        )
        
        self.client = Client()
        
        # URL for the event_registrations_full view
        self.event_registrations_full_url = reverse('event_registrations_full', kwargs={'event_id': self.event.id})

    def test_event_registrations_full_view_staff_access(self):
        # Arrange
        self.client.login(username='staff_user', password='password123')
        
        # Act
        response = self.client.get(self.event_registrations_full_url)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations_full.html')

    def test_event_registrations_full_view_non_staff_denied(self):
        # Arrange
        self.client.login(username='regular_user', password='password123')
        
        # Act
        response = self.client.get(self.event_registrations_full_url)
        
        # Assert
        self.assertEqual(response.status_code, 403)  # Permission denied status code 