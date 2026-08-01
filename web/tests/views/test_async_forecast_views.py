from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from waffle.testutils import override_flag

from backoffice.models import Event, Forecast, Program, Ride, Route
from backoffice.services.forecast_service import YOW_LOCATION


class AsyncForecastTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.program = Program.objects.create(name='Test Program')
        self.route = Route.objects.create(name='Test Route')
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.latitude, self.longitude = YOW_LOCATION
        self.event = self._create_event()

    def _create_event(self, name='Test Event', starts_at=None, virtual=False):
        starts_at = starts_at or self.starts_at
        event = Event.objects.create(
            program=self.program,
            name=name,
            description='Description',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            virtual=virtual,
        )
        Ride.objects.create(name=f'{name} ride', event=event, route=self.route)
        return event

    def _create_forecast(self):
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.starts_at + timedelta(hours=1),
            hourly=[
                {'time': self.starts_at.isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            ],
        )

    def _make_stale(self, forecast):
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=timezone.now() - timedelta(hours=2)
        )


@override_flag('weather_forecast_badges', active=True)
class EventForecastBadgeAsyncTests(AsyncForecastTestCase):

    @override_flag('async_forecast_fetch', active=True)
    def test_enqueues_a_task_instead_of_fetching_on_the_request_path(self):
        # Arrange
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay, \
                patch('backoffice.services.forecast_service.requests.get') as get:
            self.client.get(url)

        # Assert
        delay.assert_called_once()
        get.assert_not_called()

    @override_flag('async_forecast_fetch', active=True)
    def test_renders_a_re_arming_loading_badge_while_the_forecast_is_pending(self):
        # Arrange
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertContains(response, 'attempt=1')
        self.assertContains(response, 'delay:2s')

    @override_flag('async_forecast_fetch', active=True)
    def test_stops_polling_after_the_maximum_number_of_attempts(self):
        # Arrange
        url = f"{reverse('event_forecast_badge', args=[self.event.id])}?attempt=5"

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertNotContains(response, 'attempt=6')

    @override_flag('async_forecast_fetch', active=True)
    def test_renders_a_cached_forecast_without_waiting_for_the_task(self):
        # Arrange
        forecast = self._create_forecast()
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertContains(response, f'forecast-hourly-{forecast.pk}')

    @override_flag('async_forecast_fetch', active=True)
    def test_serves_a_stale_cached_forecast_while_the_refresh_is_queued(self):
        # Arrange
        forecast = self._create_forecast()
        self._make_stale(forecast)
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            response = self.client.get(url)

        # Assert
        self.assertContains(response, f'forecast-hourly-{forecast.pk}')
        delay.assert_called_once()

    @override_flag('async_forecast_fetch', active=True)
    def test_does_not_poll_for_a_virtual_event(self):
        # Arrange
        virtual_event = self._create_event(name='Virtual Event', virtual=True)
        url = reverse('event_forecast_badge', args=[virtual_event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            response = self.client.get(url)

        # Assert
        self.assertNotContains(response, 'attempt=1')
        self.assertNotContains(response, 'wx-loading')
        delay.assert_not_called()

    @override_flag('async_forecast_fetch', active=True)
    def test_does_not_poll_for_an_event_beyond_the_forecast_horizon(self):
        # Arrange
        distant_event = self._create_event(
            name='Distant Event', starts_at=self.starts_at + timedelta(days=30)
        )
        url = reverse('event_forecast_badge', args=[distant_event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            response = self.client.get(url)

        # Assert
        self.assertNotContains(response, 'attempt=1')
        self.assertNotContains(response, 'wx-loading')
        delay.assert_not_called()

    @override_flag('async_forecast_fetch', active=True)
    def test_does_not_enqueue_a_duplicate_task_while_one_is_in_flight(self):
        # Arrange
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            self.client.get(url)
            self.client.get(f'{url}?attempt=1')
            self.client.get(f'{url}?attempt=2')

        # Assert
        delay.assert_called_once()

    def test_falls_back_to_synchronous_fetching_when_the_flag_is_off(self):
        # Arrange
        url = reverse('event_forecast_badge', args=[self.event.id])

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay, \
                patch('backoffice.services.event_service.EventService.fetch_current_forecast') as fetch:
            fetch.return_value = None
            self.client.get(url)

        # Assert
        fetch.assert_called_once()
        delay.assert_not_called()


@override_flag('weather_forecast_badges', active=True)
class UpcomingForecastBadgesAsyncTests(AsyncForecastTestCase):

    @override_flag('async_forecast_fetch', active=True)
    def test_enqueues_a_task_instead_of_fetching_on_the_request_path(self):
        # Arrange
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay, \
                patch('backoffice.services.forecast_service.requests.get') as get:
            self.client.get(url)

        # Assert
        delay.assert_called_once()
        get.assert_not_called()

    @override_flag('async_forecast_fetch', active=True)
    def test_re_arms_the_poller_while_forecasts_are_pending(self):
        # Arrange
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertContains(response, 'forecast-badges-poller')
        self.assertContains(response, 'attempt=1')

    @override_flag('async_forecast_fetch', active=True)
    def test_does_not_delete_pending_badges_while_still_polling(self):
        # Arrange
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertNotContains(response, 'hx-swap-oob="delete"')

    @override_flag('async_forecast_fetch', active=True)
    def test_deletes_pending_badges_once_polling_is_exhausted(self):
        # Arrange
        url = f"{reverse('upcoming_forecast_badges')}?attempt=5"

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertContains(response, 'hx-swap-oob="delete"')
        self.assertNotContains(response, 'forecast-badges-poller')

    @override_flag('async_forecast_fetch', active=True)
    def test_stops_polling_once_every_forecast_is_cached(self):
        # Arrange
        self._create_forecast()
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay'):
            response = self.client.get(url)

        # Assert
        self.assertNotContains(response, 'forecast-badges-poller')

    @override_flag('async_forecast_fetch', active=True)
    def test_does_not_enqueue_duplicate_tasks_across_poll_attempts(self):
        # Arrange
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            self.client.get(url)
            self.client.get(f'{url}?attempt=1')
            self.client.get(f'{url}?attempt=2')

        # Assert
        delay.assert_called_once()

    @override_flag('async_forecast_fetch', active=True)
    def test_enqueues_one_task_per_window_for_events_sharing_a_window(self):
        # Arrange
        self._create_event(name='Second Event')
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay:
            self.client.get(url)

        # Assert
        delay.assert_called_once()

    def test_falls_back_to_synchronous_fetching_when_the_flag_is_off(self):
        # Arrange
        url = reverse('upcoming_forecast_badges')

        # Act
        with patch('backoffice.tasks.fetch_forecast.delay') as delay, \
                patch('backoffice.services.event_service.EventService.fetch_forecasts') as fetch:
            fetch.return_value = {}
            self.client.get(url)

        # Assert
        fetch.assert_called_once()
        delay.assert_not_called()
