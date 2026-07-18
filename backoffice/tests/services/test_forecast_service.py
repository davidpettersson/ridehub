from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Forecast, Program, Ride, Route
from backoffice.services.forecast_service import (
    AIR_QUALITY_URL,
    ForecastService,
    WEATHER_URL,
    YOW_LOCATION,
)


def _mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _weather_payload(time, weather_code=0, temperature_min=5.4, temperature_max=15.6):
    hour_key = time.strftime('%Y-%m-%dT%H:%M')
    date_key = time.strftime('%Y-%m-%d')
    return {
        'utc_offset_seconds': 0,
        'hourly': {
            'time': [hour_key],
            'weather_code': [weather_code],
        },
        'daily': {
            'time': [date_key],
            'temperature_2m_min': [temperature_min],
            'temperature_2m_max': [temperature_max],
        },
    }


def _air_quality_payload(time, aqi=42):
    hour_key = time.strftime('%Y-%m-%dT%H:%M')
    return {
        'utc_offset_seconds': 0,
        'hourly': {
            'time': [hour_key],
            'us_aqi': [aqi],
        },
    }


def _mock_get(time, weather_code=0, temperature_min=5.4, temperature_max=15.6, aqi=42):
    def side_effect(url, **kwargs):
        if url == WEATHER_URL:
            return _mock_response(_weather_payload(time, weather_code, temperature_min, temperature_max))
        if url == AIR_QUALITY_URL:
            return _mock_response(_air_quality_payload(time, aqi))
        raise AssertionError(f'Unexpected URL {url}')
    return side_effect


class ForecastServiceTestCase(TestCase):
    def setUp(self):
        self.service = ForecastService()
        self.latitude, self.longitude = YOW_LOCATION
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )

    def test_fetches_and_stores_forecast(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, weather_code=95, aqi=17)

            # Act
            forecast = self.service.get_forecast(
                self.latitude, self.longitude, self.starts_at + timedelta(minutes=25)
            )

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast.time, self.starts_at)
        self.assertEqual(forecast.precipitation, Forecast.Precipitation.THUNDER)
        self.assertEqual(forecast.temperature_min, 5)
        self.assertEqual(forecast.temperature_max, 16)
        self.assertEqual(forecast.aqi, 17)
        self.assertEqual(Forecast.objects.count(), 1)

    def test_fresh_forecast_returned_without_fetching(self):
        # Arrange
        Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            time=self.starts_at,
            precipitation=Forecast.Precipitation.SUN,
            temperature_min=5,
            temperature_max=15,
            aqi=42,
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertIsNotNone(forecast)
        mock_get.assert_not_called()

    def test_stale_forecast_refetched_and_updated_in_place(self):
        # Arrange
        stale = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            time=self.starts_at,
            precipitation=Forecast.Precipitation.SUN,
            temperature_min=5,
            temperature_max=15,
            aqi=42,
        )
        Forecast.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, weather_code=61, aqi=99)

            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertEqual(forecast.pk, stale.pk)
        self.assertEqual(forecast.precipitation, Forecast.Precipitation.RAIN)
        self.assertEqual(forecast.aqi, 99)
        self.assertEqual(Forecast.objects.count(), 1)

    def test_start_times_in_same_hour_share_forecast(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at)

            # Act
            first = self.service.get_forecast(
                self.latitude, self.longitude, self.starts_at + timedelta(minutes=1)
            )
            second = self.service.get_forecast(
                self.latitude, self.longitude, self.starts_at + timedelta(minutes=55)
            )

        # Assert
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(Forecast.objects.count(), 1)

    def test_past_event_returns_none(self):
        # Arrange
        past = timezone.now() - timedelta(hours=2)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, past)

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_event_beyond_window_returns_none(self):
        # Arrange
        far_future = timezone.now() + timedelta(days=5)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, far_future)

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_fetch_failure_returns_stale_forecast(self):
        # Arrange
        stale = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            time=self.starts_at,
            precipitation=Forecast.Precipitation.CLOUD,
            temperature_min=5,
            temperature_max=15,
            aqi=42,
        )
        Forecast.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError('boom')

            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertEqual(forecast.pk, stale.pk)

    def test_fetch_failure_without_stored_forecast_returns_none(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError('boom')

            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertIsNone(forecast)

    def test_precipitation_mapping_from_weather_codes(self):
        # Arrange
        expectations = {
            0: Forecast.Precipitation.SUN,
            1: Forecast.Precipitation.SUN,
            2: Forecast.Precipitation.CLOUD,
            45: Forecast.Precipitation.CLOUD,
            51: Forecast.Precipitation.RAIN,
            75: Forecast.Precipitation.RAIN,
            86: Forecast.Precipitation.RAIN,
            95: Forecast.Precipitation.THUNDER,
            99: Forecast.Precipitation.THUNDER,
        }

        for code, expected in expectations.items():
            # Act
            result = ForecastService._precipitation_from_weather_code(code)

            # Assert
            self.assertEqual(result, expected, f'weather code {code}')


class ForecastServiceEventsTestCase(TestCase):
    def setUp(self):
        self.service = ForecastService()
        self.program = Program.objects.create(name='Test Program')
        self.route = Route.objects.create(name='Test Route')
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )

    def _create_event(self, name, starts_at, with_ride=True, cancelled=False):
        event = Event.objects.create(
            program=self.program,
            name=name,
            description='Description',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
        )
        if with_ride:
            Ride.objects.create(name=f'{name} ride', event=event, route=self.route)
        if cancelled:
            event.cancel()
            event.save()
        return event

    def test_events_in_same_hour_trigger_single_fetch(self):
        # Arrange
        first = self._create_event('First', self.starts_at + timedelta(minutes=1))
        second = self._create_event('Second', self.starts_at + timedelta(minutes=55))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at)

            # Act
            forecasts = self.service.get_forecasts_for_events([first, second])

        # Assert
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(forecasts[first.id].pk, forecasts[second.id].pk)

    def test_events_without_rides_skipped(self):
        # Arrange
        event = self._create_event('No rides', self.starts_at, with_ride=False)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecasts = self.service.get_forecasts_for_events([event])

        # Assert
        self.assertEqual(forecasts, {})
        mock_get.assert_not_called()

    def test_cancelled_events_skipped(self):
        # Arrange
        event = self._create_event('Cancelled', self.starts_at, cancelled=True)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecasts = self.service.get_forecasts_for_events([event])

        # Assert
        self.assertEqual(forecasts, {})
        mock_get.assert_not_called()

    def test_events_outside_window_excluded(self):
        # Arrange
        event = self._create_event('Far out', timezone.now() + timedelta(days=5))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecasts = self.service.get_forecasts_for_events([event])

        # Assert
        self.assertEqual(forecasts, {})
        mock_get.assert_not_called()
