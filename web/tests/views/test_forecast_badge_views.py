from datetime import timedelta, timezone as datetime_timezone
from unittest.mock import patch

import requests

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from waffle.testutils import override_flag

from backoffice.models import Event, Forecast, Program, Ride, Route
from backoffice.services.forecast_service import YOW_LOCATION


def _hour_label(time):
    return f"{int(time.strftime('%I'))} {time.strftime('%p')}"


def _local_hour_today(hour):
    local = timezone.localtime(timezone.now()).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return local.astimezone(datetime_timezone.utc)


class ForecastBadgeTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.route = Route.objects.create(name='Test Route')
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.latitude, self.longitude = YOW_LOCATION

    def _create_event(self, name='Test Event', starts_at=None, with_ride=True, virtual=False):
        starts_at = starts_at or self.starts_at
        event = Event.objects.create(
            program=self.program,
            name=name,
            description='Description',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            virtual=virtual,
        )
        if with_ride:
            Ride.objects.create(name=f'{name} ride', event=event, route=self.route)
        return event

    def _create_forecast(self, time=None, hourly=None):
        time = time or self.starts_at
        hourly = hourly or [
            {'time': time.isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            {'time': (time + timedelta(hours=1)).isoformat(), 'condition': 'cloud', 'temperature': 15, 'aqhi': 5},
        ]
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=time,
            end_time=time + timedelta(hours=1),
            hourly=hourly,
        )

    def _make_stale(self, forecast):
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=timezone.now() - timedelta(hours=2)
        )


class UpcomingPageForecastPlaceholderTests(ForecastBadgeTestCase):
    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_placeholder_without_fetching_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, reverse('upcoming_forecast_badges'))
        self.assertContains(response, 'Loading weather forecast')
        self.assertContains(response, 'wx-shimmer')
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_renders_badge_inline_when_fresh_forecast_cached(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '12–15&deg;')
        self.assertContains(response, f'id="forecast-badge-{event.id}"')
        self.assertNotContains(response, 'Loading weather forecast')
        self.assertNotContains(response, reverse('upcoming_forecast_badges'))
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_placeholder_when_cached_forecast_stale(self):
        # Arrange
        event = self._create_event()
        self._make_stale(self._create_forecast())

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, reverse('upcoming_forecast_badges'))
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=False)
    def test_upcoming_hides_placeholder_when_flag_disabled(self):
        # Arrange
        event = self._create_event()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, reverse('upcoming_forecast_badges'))

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_hides_placeholder_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, reverse('upcoming_forecast_badges'))

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_placeholder_for_ongoing_event(self):
        # Arrange
        now = _local_hour_today(12)
        event = self._create_event(starts_at=now - timedelta(minutes=30))

        # Act
        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, 'Loading weather forecast')

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_hides_placeholder_for_event_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )
        event = self._create_event(starts_at=far_starts_at)

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, reverse('upcoming_forecast_badges'))


class UpcomingForecastBadgesViewTests(ForecastBadgeTestCase):
    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_returns_badge_for_event_with_ride(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertContains(response, f'id="forecast-badge-{event.id}"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '12–15&deg;')
        self.assertNotContains(response, '(beta)')
        self.assertNotContains(response, '\U0001F327')
        self.assertContains(response, 'Open-Meteo')

    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_shows_single_temperature_when_within_two_degree_span(self):
        # Arrange
        self._create_event()
        self._create_forecast(hourly=[
            {'time': self.starts_at.isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            {'time': (self.starts_at + timedelta(hours=1)).isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
        ])

        # Act
        response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertContains(response, '12&deg;')
        self.assertNotContains(response, '12–12')

    @override_flag('weather_forecast_badges', active=False)
    def test_badges_endpoint_returns_nothing_when_flag_disabled(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertEqual(response.content.strip(), b'')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_returns_badge_for_event_without_rides(self):
        # Arrange
        self._create_event(with_ride=False)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_skips_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_deletes_placeholder_when_forecast_unavailable(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get', side_effect=requests.RequestException('down')):
            response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertContains(response, f'id="forecast-badge-{event.id}"')
        self.assertContains(response, 'hx-swap-oob="delete"')
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_badges_endpoint_has_no_forecast_history_link(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming_forecast_badges'))

        # Assert
        self.assertNotContains(response, 'View forecast history')


class DetailPageForecastPlaceholderTests(ForecastBadgeTestCase):
    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_placeholder_without_fetching_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, reverse('event_forecast_badge', args=[event.id]))
        self.assertContains(response, 'Loading weather forecast')
        self.assertContains(response, 'wx-shimmer')
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_renders_badge_inline_when_fresh_forecast_cached(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '(beta)')
        self.assertContains(response, 'View forecast history')
        self.assertNotContains(response, 'Loading weather forecast')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_placeholder_when_cached_forecast_stale(self):
        # Arrange
        event = self._create_event()
        self._make_stale(self._create_forecast())

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'Loading weather forecast')
        self.assertContains(response, reverse('event_forecast_badge', args=[event.id]))
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=False)
    def test_detail_hides_placeholder_when_flag_disabled(self):
        # Arrange
        event = self._create_event()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_placeholder_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_placeholder_for_event_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )
        event = self._create_event(starts_at=far_starts_at)

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_placeholder_for_ongoing_event(self):
        # Arrange
        now = _local_hour_today(12)
        event = self._create_event(starts_at=now - timedelta(minutes=30))

        # Act
        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, 'Loading weather forecast')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_placeholder_for_event_finished_earlier_today(self):
        # Arrange
        now = _local_hour_today(20)
        event = self._create_event(starts_at=now - timedelta(hours=12))

        # Act
        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, 'Loading weather forecast')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_placeholder_for_event_on_an_earlier_day(self):
        # Arrange
        event = self._create_event(starts_at=_local_hour_today(12) - timedelta(days=1))

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_renders_hourly_times_in_the_configured_timezone(self):
        # Arrange
        hour = self.starts_at.astimezone(datetime_timezone.utc).replace(hour=16)
        event = self._create_event(starts_at=hour)
        self._create_forecast(time=hour)

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, _hour_label(timezone.localtime(hour)))
        self.assertNotContains(response, _hour_label(hour))

    @override_settings(TIME_ZONE='America/Vancouver')
    @override_flag('weather_forecast_badges', active=True)
    def test_detail_renders_hourly_times_in_a_western_timezone(self):
        # Arrange
        hour = self.starts_at.astimezone(datetime_timezone.utc).replace(hour=16)
        event = self._create_event(starts_at=hour)
        self._create_forecast(time=hour)

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, _hour_label(timezone.localtime(hour)))
        self.assertNotContains(response, _hour_label(hour))

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_placeholder_for_cancelled_event(self):
        # Arrange
        event = self._create_event()
        event.cancel()
        event.save()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')


class RegistrationPagesForecastBadgeTests(ForecastBadgeTestCase):
    @override_flag('weather_forecast_badges', active=True)
    def test_registrations_renders_badge_inline_when_fresh_forecast_cached(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('riders_list', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertNotContains(response, 'Loading weather forecast')

    @override_flag('weather_forecast_badges', active=True)
    def test_registrations_shows_placeholder_without_fetching_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('riders_list', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, reverse('event_forecast_badge', args=[event.id]))
        self.assertContains(response, 'Loading weather forecast')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=False)
    def test_registrations_hides_badge_when_flag_disabled(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('riders_list', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_registration_form_renders_badge_inline_when_fresh_forecast_cached(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('registration_create', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertNotContains(response, 'Loading weather forecast')

    @override_flag('weather_forecast_badges', active=True)
    def test_registration_form_shows_placeholder_without_fetching_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('registration_create', args=[event.id]))

        # Assert
        self.assertContains(response, f'forecast-badge-{event.id}')
        self.assertContains(response, reverse('event_forecast_badge', args=[event.id]))
        self.assertContains(response, 'Loading weather forecast')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=False)
    def test_registration_form_hides_badge_when_flag_disabled(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('registration_create', args=[event.id]))

        # Assert
        self.assertNotContains(response, f'forecast-badge-{event.id}')
        self.assertNotContains(response, 'AQHI')


class EventForecastBadgeViewTests(ForecastBadgeTestCase):
    @override_flag('weather_forecast_badges', active=True)
    def test_badge_endpoint_returns_expandable_badge(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '(beta)')
        self.assertContains(response, 'data-bs-toggle="modal"')

    @override_flag('weather_forecast_badges', active=True)
    def test_badge_endpoint_includes_forecast_history_link(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertContains(response, reverse('event_forecasts', args=[event.id]))
        self.assertContains(response, 'View forecast history')

    @override_flag('weather_forecast_badges', active=True)
    def test_badge_endpoint_returns_nothing_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=False)
    def test_badge_endpoint_returns_nothing_when_flag_disabled(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_badge_endpoint_returns_nothing_for_event_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )
        event = self._create_event(starts_at=far_starts_at)

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_badge_endpoint_returns_badge_for_cancelled_event(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()
        event.cancel()
        event.save()

        # Act
        response = self.client.get(reverse('event_forecast_badge', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
