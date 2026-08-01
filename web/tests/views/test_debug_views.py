from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class DebugTriggerTaskTests(TestCase):

    def setUp(self):
        self.url = reverse('debug_trigger_task')
        self.staff = User.objects.create_user(
            username='staff', email='staff@example.com', password='password', is_staff=True
        )
        self.rider = User.objects.create_user(
            username='rider', email='rider@example.com', password='password'
        )

    def test_staff_can_trigger_the_task(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            response = self.client.post(self.url, {'message': 'hello'})

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'task_id': 'task-123', 'message': 'hello'})
        delay.assert_called_once_with('hello')

    def test_message_defaults_to_ping(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            self.client.post(self.url)

        # Assert
        delay.assert_called_once_with('ping')

    def test_non_staff_cannot_trigger_the_task(self):
        # Arrange
        self.client.force_login(self.rider)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()

    def test_anonymous_user_cannot_trigger_the_task(self):
        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()

    def test_get_is_not_allowed(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 405)
        delay.assert_not_called()
