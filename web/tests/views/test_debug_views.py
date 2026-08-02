from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Forecast


class DebugViewTestCase(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='password'
        )
        self.staff = User.objects.create_user(
            username='staff', email='staff@example.com', password='password', is_staff=True
        )
        self.rider = User.objects.create_user(
            username='rider', email='rider@example.com', password='password'
        )


class DebugIndexTests(DebugViewTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('debug_index')

    def test_superuser_sees_links_to_the_debug_pages(self):
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('debug_tasks_ping'))
        self.assertContains(response, reverse('debug_forecasts'))

    def test_staff_cannot_reach_the_page(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_reach_the_page(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)


class DebugTasksPingTests(DebugViewTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('debug_tasks_ping')

    def test_the_page_lives_at_debug_tasks_ping(self):
        # Assert
        self.assertEqual(self.url, '/debug/tasks-ping')

    def test_superuser_sees_a_form_without_queueing_anything(self):
        # Arrange
        self.client.force_login(self.superuser)

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
        self.client.force_login(self.superuser)

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
        self.client.force_login(self.superuser)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            self.client.post(self.url, {'message': '   '})

        # Assert
        delay.assert_called_once_with('ping')

    def test_long_messages_are_truncated(self):
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.return_value.id = 'task-123'
            self.client.post(self.url, {'message': 'x' * 500})

        # Assert
        delay.assert_called_once_with('x' * 200)

    def test_shows_an_error_when_the_broker_is_unreachable(self):
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            delay.side_effect = ConnectionError('Connection refused')
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Could not queue the task')
        self.assertContains(response, 'Connection refused')

    def test_staff_who_are_not_superusers_cannot_reach_the_page(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.debug_ping.delay') as delay:
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()

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


class DebugForecastsTests(DebugViewTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('debug_forecasts')

    def _create_forecast(self, start_time) -> Forecast:
        return Forecast.objects.create(
            latitude=Decimal('45.32250'),
            longitude=Decimal('-75.66920'),
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            hourly=[{
                'time': start_time.isoformat(),
                'condition': Forecast.Condition.SUN,
                'temperature': 20.0,
                'aqhi': 3,
            }],
        )

    def test_the_page_lives_at_debug_forecasts(self):
        # Assert
        self.assertEqual(self.url, '/debug/forecasts')

    def test_superuser_sees_the_most_recent_forecasts(self):
        # Arrange
        self.client.force_login(self.superuser)
        start_time = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        forecast = self._create_forecast(start_time)

        # Act
        with patch('web.views.debug.refresh_forecasts.delay') as delay:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refresh forecasts')
        self.assertContains(response, str(forecast.latitude))
        delay.assert_not_called()

    def test_forecasts_are_listed_newest_first(self):
        # Arrange
        self.client.force_login(self.superuser)
        start_time = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        older = self._create_forecast(start_time)
        newer = self._create_forecast(start_time + timedelta(days=1))

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(list(response.context['forecasts']), [newer, older])

    def test_submitting_the_form_queues_the_refresh(self):
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        with patch('web.views.debug.refresh_forecasts.delay') as delay:
            delay.return_value.id = 'task-456'
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'task-456')
        delay.assert_called_once_with()

    def test_shows_an_error_when_the_broker_is_unreachable(self):
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        with patch('web.views.debug.refresh_forecasts.delay') as delay:
            delay.side_effect = ConnectionError('Connection refused')
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Could not queue the task')
        self.assertContains(response, 'Connection refused')

    def test_staff_who_are_not_superusers_cannot_reach_the_page(self):
        # Arrange
        self.client.force_login(self.staff)

        # Act
        with patch('web.views.debug.refresh_forecasts.delay') as delay:
            response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()

    def test_anonymous_user_cannot_reach_the_page(self):
        # Act
        with patch('web.views.debug.refresh_forecasts.delay') as delay:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 302)
        delay.assert_not_called()
