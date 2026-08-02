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

    def test_staff_sees_a_form_without_queueing_anything(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="post"')
        self.assertContains(response, 'Queue task')
        delay.assert_not_called()

    def test_submitting_the_form_queues_the_task(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            response = self.client.post(self.url, {'message': 'hello'})

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'task-123')
        self.assertContains(response, 'hello')
        delay.assert_called_once_with('hello')

    def test_message_defaults_to_ping_when_left_blank(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            self.client.post(self.url, {'message': '   '})

        # Assert
        delay.assert_called_once_with('ping')

    def test_long_messages_are_truncated(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            self.client.post(self.url, {'message': 'x' * 500})

        # Assert
        delay.assert_called_once_with('x' * 200)

    def test_shows_an_error_when_the_broker_is_unreachable(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.side_effect = ConnectionError('Connection refused')
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Could not queue the task')
        self.assertContains(response, 'Connection refused')

    def test_non_staff_cannot_reach_the_page(self):
        # Arrange
        self.client.force_login(self.rider)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()

    def test_anonymous_user_cannot_reach_the_page(self):
        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()
