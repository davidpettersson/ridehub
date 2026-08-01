from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class ProfileEmergencyContactTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rider@example.com',
            email='rider@example.com',
            password='secret',
            first_name='Rita',
            last_name='Rider',
        )
        self.client.force_login(self.user)

    def test_emergency_contact_details_are_shown(self):
        # Arrange
        self.user.profile.emergency_contact_name = 'Erin Emergency'
        self.user.profile.emergency_contact_phone = '+16135551234'
        self.user.profile.save()

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertContains(response, 'Emergency contact')
        self.assertContains(response, 'Erin Emergency')
        self.assertContains(response, 'Emergency phone')
        self.assertContains(response, '(613) 555-1234')

    def test_emergency_contact_details_are_not_provided(self):
        # Arrange
        self.user.profile.emergency_contact_name = ''
        self.user.profile.emergency_contact_phone = ''
        self.user.profile.save()

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertContains(response, 'Emergency contact')
        self.assertContains(response, 'Not provided', count=3)
