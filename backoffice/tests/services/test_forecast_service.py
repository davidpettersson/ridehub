from datetime import timedelta
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


def _air_quality_payload(time, pm2_5=8.0, nitrogen_dioxide=15.0, ozone=60.0):
    hours = [time - timedelta(hours=2), time - timedelta(hours=1), time]
    return {
        'utc_offset_seconds': 0,
        'hourly': {
            'time': [h.strftime('%Y-%m-%dT%H:%M') for h in hours],
            'pm2_5': [pm2_5] * 3,
            'nitrogen_dioxide': [nitrogen_dioxide] * 3,
            'ozone': [ozone] * 3,
        },
    }


def _mock_get(time, weather_code=0, temperature_min=5.4, temperature_max=15.6,
              pm2_5=8.0, nitrogen_dioxide=15.0, ozone=60.0):
    def side_effect(url, **kwargs):
        if url == WEATHER_URL:
            return _mock_response(_weather_payload(time, weather_code, temperature_min, temperature_max))
        if url == AIR_QUALITY_URL:
            return _mock_response(_air_quality_payload(time, pm2_5, nitrogen_dioxide, ozone))
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
            mock_get.side_effect = _mock_get(self.starts_at, weather_code=95)

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
        self.assertEqual(forecast.aqhi, 3)
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
            aqhi=3,
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
            aqhi=3,
        )
        Forecast.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(
                self.starts_at, weather_code=61, pm2_5=100.0, nitrogen_dioxide=40.0, ozone=120.0
            )

            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertEqual(forecast.pk, stale.pk)
        self.assertEqual(forecast.precipitation, Forecast.Precipitation.RAIN)
        self.assertEqual(forecast.aqhi, 10)
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

    def test_event_four_days_out_within_window(self):
        # Arrange
        starts_at = (timezone.now() + timedelta(days=4)).replace(minute=0, second=0, microsecond=0)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(starts_at)

            # Act
            forecast = self.service.get_forecast(self.latitude, self.longitude, starts_at)

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast.time, starts_at)

    def test_event_beyond_window_returns_none(self):
        # Arrange
        far_future = timezone.now() + timedelta(days=7)

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
            aqhi=3,
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


class AqhiComputationTestCase(TestCase):
    def _hourly(self, pm2_5, nitrogen_dioxide, ozone):
        return {
            'pm2_5': pm2_5,
            'nitrogen_dioxide': nitrogen_dioxide,
            'ozone': ozone,
        }

    def test_clean_air_yields_minimum_of_one(self):
        # Arrange
        hourly = self._hourly([0.0] * 3, [0.0] * 3, [0.0] * 3)

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 2)

        # Assert
        self.assertEqual(aqhi, 1)

    def test_extreme_pollution_capped_at_eleven(self):
        # Arrange
        hourly = self._hourly([2000.0] * 3, [1000.0] * 3, [1000.0] * 3)

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 2)

        # Assert
        self.assertEqual(aqhi, 11)

    def test_known_reference_value(self):
        # Arrange
        hourly = self._hourly([8.0] * 3, [15.0] * 3, [60.0] * 3)

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 2)

        # Assert
        self.assertEqual(aqhi, 3)

    def test_result_is_always_valid_integer_across_input_grid(self):
        # Arrange
        concentrations = [0.0, 1.0, 10.0, 50.0, 250.0, 1000.0, 5000.0]

        for pm2_5 in concentrations:
            for nitrogen_dioxide in concentrations:
                for ozone in concentrations:
                    hourly = self._hourly([pm2_5] * 3, [nitrogen_dioxide] * 3, [ozone] * 3)

                    # Act
                    aqhi = ForecastService._compute_aqhi(hourly, 2)

                    # Assert
                    self.assertIsInstance(aqhi, int)
                    self.assertGreaterEqual(aqhi, 1)
                    self.assertLessEqual(aqhi, 11)

    def test_missing_hours_fall_back_to_available_hours(self):
        # Arrange
        hourly = self._hourly(
            [None, None, 8.0],
            [None, None, 15.0],
            [None, None, 60.0],
        )

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 2)

        # Assert
        self.assertEqual(aqhi, 3)

    def test_partial_hours_only_use_complete_triples(self):
        # Arrange
        hourly = self._hourly(
            [8.0, None, 8.0],
            [15.0, 15.0, 15.0],
            [60.0, None, 60.0],
        )

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 2)

        # Assert
        self.assertEqual(aqhi, 3)

    def test_no_pollutant_data_raises(self):
        # Arrange
        hourly = self._hourly([None] * 3, [None] * 3, [None] * 3)

        # Act & Assert
        with self.assertRaises(ValueError):
            ForecastService._compute_aqhi(hourly, 2)

    def test_hour_index_at_start_of_series_uses_single_hour(self):
        # Arrange
        hourly = self._hourly([8.0], [15.0], [60.0])

        # Act
        aqhi = ForecastService._compute_aqhi(hourly, 0)

        # Assert
        self.assertEqual(aqhi, 3)

    def test_missing_event_hour_data_surfaces_as_stale_fallback(self):
        # Arrange
        service = ForecastService()
        latitude, longitude = YOW_LOCATION
        starts_at = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)

        def side_effect(url, **kwargs):
            if url == WEATHER_URL:
                return _mock_response(_weather_payload(starts_at))
            payload = _air_quality_payload(starts_at)
            payload['hourly']['pm2_5'] = [None] * 3
            payload['hourly']['nitrogen_dioxide'] = [None] * 3
            payload['hourly']['ozone'] = [None] * 3
            return _mock_response(payload)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = side_effect

            # Act
            forecast = service.get_forecast(latitude, longitude, starts_at)

        # Assert
        self.assertIsNone(forecast)
        self.assertEqual(Forecast.objects.count(), 0)


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

    def test_cancelled_events_included(self):
        # Arrange
        event = self._create_event('Cancelled', self.starts_at, cancelled=True)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at)

            # Act
            forecasts = self.service.get_forecasts_for_events([event])

        # Assert
        self.assertIn(event.id, forecasts)

    def test_events_outside_window_excluded(self):
        # Arrange
        event = self._create_event('Far out', timezone.now() + timedelta(days=7))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecasts = self.service.get_forecasts_for_events([event])

        # Assert
        self.assertEqual(forecasts, {})
        mock_get.assert_not_called()
