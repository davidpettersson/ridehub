from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from backoffice.models import Forecast
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


def _hour_range(start, end, hours_before=0):
    hours = []
    hour = start - timedelta(hours=hours_before)
    while hour <= end:
        hours.append(hour)
        hour += timedelta(hours=1)
    return hours


def _weather_payload(start, end, weather_codes=None, temperatures=None):
    hours = _hour_range(start, end)
    return {
        'utc_offset_seconds': 0,
        'hourly': {
            'time': [h.strftime('%Y-%m-%dT%H:%M') for h in hours],
            'weather_code': weather_codes or [0] * len(hours),
            'temperature_2m': temperatures or [10.0] * len(hours),
        },
    }


def _air_quality_payload(start, end, pm2_5=8.0, nitrogen_dioxide=15.0, ozone=60.0):
    hours = _hour_range(start, end, hours_before=2)
    return {
        'utc_offset_seconds': 0,
        'hourly': {
            'time': [h.strftime('%Y-%m-%dT%H:%M') for h in hours],
            'pm2_5': [pm2_5] * len(hours),
            'nitrogen_dioxide': [nitrogen_dioxide] * len(hours),
            'ozone': [ozone] * len(hours),
        },
    }


def _mock_get(start, end, weather_codes=None, temperatures=None,
              pm2_5=8.0, nitrogen_dioxide=15.0, ozone=60.0):
    def side_effect(url, **kwargs):
        if url == WEATHER_URL:
            return _mock_response(_weather_payload(start, end, weather_codes, temperatures))
        if url == AIR_QUALITY_URL:
            return _mock_response(_air_quality_payload(start, end, pm2_5, nitrogen_dioxide, ozone))
        raise AssertionError(f'Unexpected URL {url}')
    return side_effect


def _local_hour_today(hour):
    local = timezone.localtime(timezone.now()).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return local.astimezone(datetime_timezone.utc)


def _hourly_entry(time, condition='sun', temperature=10, aqhi=3):
    return [{
        'time': time.isoformat(),
        'condition': condition,
        'temperature': temperature,
        'aqhi': aqhi,
    }]


class ForecastServiceTestCase(TestCase):
    def setUp(self):
        self.service = ForecastService()
        self.latitude, self.longitude = YOW_LOCATION
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )

    def test_fetches_and_stores_forecast_over_event_duration(self):
        # Arrange
        starts_at = self.starts_at + timedelta(minutes=25)
        ends_at = self.starts_at + timedelta(hours=2, minutes=30)
        window_end = self.starts_at + timedelta(hours=3)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(
                self.starts_at, window_end,
                weather_codes=[0, 95, 3, 0],
                temperatures=[5.4, 15.6, 10.0, 10.0],
            )

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, starts_at, ends_at)

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast.start_time, self.starts_at)
        self.assertEqual(forecast.end_time, window_end)
        self.assertEqual(len(forecast.hourly), 4)
        self.assertEqual(
            [entry['condition'] for entry in forecast.hourly],
            ['sun', 'thunder', 'cloud', 'sun'],
        )
        self.assertEqual(
            [entry['temperature'] for entry in forecast.hourly],
            [5, 16, 10, 10],
        )
        self.assertEqual([entry['aqhi'] for entry in forecast.hourly], [3, 3, 3, 3])
        self.assertEqual(Forecast.objects.count(), 1)

    def test_fresh_forecast_returned_without_fetching(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=window_end,
            hourly=_hourly_entry(self.starts_at),
        )

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            fresh = self.service.get_forecast(self.starts_at, window_end)

        # Assert
        self.assertEqual(fresh, forecast)
        mock_get.assert_not_called()

    def test_forecast_older_than_six_hours_is_not_fresh(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=window_end,
            hourly=_hourly_entry(self.starts_at),
        )
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=timezone.now() - timedelta(hours=6, minutes=1)
        )

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            fresh = self.service.get_forecast(self.starts_at, window_end)

        # Assert
        self.assertIsNone(fresh)
        mock_get.assert_not_called()

    def test_forecast_just_under_six_hours_old_is_still_fresh(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=window_end,
            hourly=_hourly_entry(self.starts_at),
        )
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=timezone.now() - timedelta(hours=5, minutes=59)
        )

        # Act
        fresh = self.service.get_forecast(self.starts_at, window_end)

        # Assert
        self.assertEqual(fresh, forecast)

    def test_past_event_keeps_a_forecast_prepared_shortly_before_it_started(self):
        # Arrange
        starts_at = _local_hour_today(9) - timedelta(days=30)
        window_end = starts_at + timedelta(hours=1)
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=starts_at,
            end_time=window_end,
            hourly=_hourly_entry(starts_at),
        )
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=starts_at - timedelta(hours=5)
        )

        # Act
        displayed = self.service.get_forecast(starts_at, window_end)

        # Assert
        self.assertEqual(displayed, forecast)

    def test_past_event_drops_a_forecast_prepared_long_before_it_started(self):
        # Arrange
        starts_at = _local_hour_today(9) - timedelta(days=30)
        window_end = starts_at + timedelta(hours=1)
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=starts_at,
            end_time=window_end,
            hourly=_hourly_entry(starts_at),
        )
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=starts_at - timedelta(hours=7)
        )

        # Act
        displayed = self.service.get_forecast(starts_at, window_end)

        # Assert
        self.assertIsNone(displayed)

    def test_past_event_uses_the_last_forecast_prepared_before_it_started(self):
        # Arrange
        starts_at = _local_hour_today(9) - timedelta(days=30)
        window_end = starts_at + timedelta(hours=1)
        common = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_time': starts_at,
            'end_time': window_end,
        }
        earlier = Forecast.objects.create(hourly=_hourly_entry(starts_at, condition='rain'), **common)
        Forecast.objects.filter(pk=earlier.pk).update(
            prepared_at=starts_at - timedelta(hours=5)
        )
        latest = Forecast.objects.create(hourly=_hourly_entry(starts_at, condition='sun'), **common)
        Forecast.objects.filter(pk=latest.pk).update(
            prepared_at=starts_at - timedelta(hours=1)
        )

        # Act
        displayed = self.service.get_forecast(starts_at, window_end)

        # Assert
        self.assertEqual(displayed, latest)

    def test_no_stored_forecast_yields_no_fresh_forecast(self):
        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            fresh = self.service.get_forecast(self.starts_at)

        # Assert
        self.assertIsNone(fresh)
        mock_get.assert_not_called()

    def test_no_fresh_forecast_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            fresh = self.service.get_forecast(far_starts_at)

        # Assert
        self.assertIsNone(fresh)
        mock_get.assert_not_called()

    def test_air_quality_entirely_unavailable_still_produces_forecast(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)

        def side_effect(url, **kwargs):
            if url == WEATHER_URL:
                return _mock_response(_weather_payload(self.starts_at, window_end))
            unrelated_start = self.starts_at - timedelta(days=3)
            unrelated_end = unrelated_start + timedelta(hours=1)
            return _mock_response(_air_quality_payload(unrelated_start, unrelated_end))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = side_effect

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(len(forecast.hourly), 2)
        self.assertTrue(all(entry['aqhi'] is None for entry in forecast.hourly))

    def test_air_quality_partially_available_keeps_hours_with_data(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=2)

        def side_effect(url, **kwargs):
            if url == WEATHER_URL:
                return _mock_response(_weather_payload(self.starts_at, window_end))
            partial_end = self.starts_at + timedelta(hours=1)
            return _mock_response(_air_quality_payload(self.starts_at, partial_end))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = side_effect

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at, window_end)

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual([entry['aqhi'] is not None for entry in forecast.hourly], [True, True, False])

    def test_missing_end_defaults_to_one_hour_window(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=1))

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertEqual(forecast.end_time, self.starts_at + timedelta(hours=1))

    def test_refresh_always_fetches_even_when_a_fresh_forecast_exists(self):
        # Arrange
        existing = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.starts_at + timedelta(hours=1),
            hourly=_hourly_entry(self.starts_at, condition='sun'),
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=1))

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertNotEqual(forecast.pk, existing.pk)
        self.assertEqual(Forecast.objects.count(), 2)

    def test_same_start_different_end_uses_separate_forecasts(self):
        # Arrange
        short_end = self.starts_at + timedelta(hours=1)
        long_end = self.starts_at + timedelta(hours=4)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, long_end)

            # Act
            short = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at, short_end)
            long = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at, long_end)

        # Assert
        self.assertNotEqual(short.pk, long.pk)
        self.assertEqual(Forecast.objects.count(), 2)

    def test_stale_forecast_refetched_as_new_record_preserving_old(self):
        # Arrange
        stale = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.starts_at + timedelta(hours=1),
            hourly=_hourly_entry(self.starts_at, condition='sun'),
        )
        Forecast.objects.filter(pk=stale.pk).update(
            prepared_at=timezone.now() - timedelta(hours=2)
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(
                self.starts_at, self.starts_at + timedelta(hours=1),
                weather_codes=[61, 61],
                pm2_5=100.0, nitrogen_dioxide=40.0, ozone=120.0,
            )

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertNotEqual(forecast.pk, stale.pk)
        self.assertEqual([entry['condition'] for entry in forecast.hourly], ['rain', 'rain'])
        self.assertEqual([entry['aqhi'] for entry in forecast.hourly], [10, 10])
        self.assertEqual(Forecast.objects.count(), 2)
        stale.refresh_from_db()
        self.assertEqual(stale.hourly[0]['condition'], 'sun')

    def test_latest_forecast_returned_when_multiple_exist_for_window(self):
        # Arrange
        common = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_time': self.starts_at,
            'end_time': self.starts_at + timedelta(hours=1),
        }
        old = Forecast.objects.create(hourly=_hourly_entry(self.starts_at, condition='rain'), **common)
        Forecast.objects.filter(pk=old.pk).update(
            prepared_at=timezone.now() - timedelta(minutes=30)
        )
        newer = Forecast.objects.create(hourly=_hourly_entry(self.starts_at, condition='sun'), **common)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecast = self.service.get_forecast(self.starts_at)

        # Assert
        self.assertEqual(forecast.pk, newer.pk)
        mock_get.assert_not_called()

    def test_start_times_in_same_hour_share_a_window(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=1))

            # Act
            first = self.service.refresh_forecast(
                self.latitude, self.longitude, self.starts_at + timedelta(minutes=1)
            )
            second = self.service.refresh_forecast(
                self.latitude, self.longitude, self.starts_at + timedelta(minutes=55)
            )

        # Assert
        self.assertEqual(first.start_time, second.start_time)
        self.assertEqual(first.end_time, second.end_time)

    def test_missing_trailing_hours_still_produce_forecast_for_requested_window(self):
        # Arrange
        available_end = self.starts_at + timedelta(hours=1)
        requested_end = self.starts_at + timedelta(hours=6)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, available_end)

            # Act
            forecast = self.service.refresh_forecast(
                self.latitude, self.longitude, self.starts_at, requested_end
            )

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast.end_time, requested_end)

    def test_end_time_clamped_to_forecast_window_horizon(self):
        # Arrange
        before = timezone.now()
        requested_end = self.starts_at + timedelta(days=30)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=2))

            # Act
            forecast = self.service.refresh_forecast(
                self.latitude, self.longitude, self.starts_at, requested_end
            )

        # Assert
        after = timezone.now()
        expected = {
            ForecastService._snap_to_hour_ceiling(before + timedelta(days=7)),
            ForecastService._snap_to_hour_ceiling(after + timedelta(days=7)),
        }
        self.assertIn(forecast.end_time, expected)

    def test_ongoing_event_is_not_refetched(self):
        # Arrange
        now = _local_hour_today(12)
        starts_at = now - timedelta(hours=1)
        ends_at = now + timedelta(hours=1)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(
                    self.latitude, self.longitude, starts_at, ends_at
                )

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_event_finished_earlier_today_is_not_refetched(self):
        # Arrange
        now = _local_hour_today(20)
        starts_at = now - timedelta(hours=12)
        ends_at = starts_at + timedelta(hours=2)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(
                    self.latitude, self.longitude, starts_at, ends_at
                )

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_event_on_an_earlier_day_returns_none(self):
        # Arrange
        now = _local_hour_today(12)
        past = now - timedelta(days=1)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(self.latitude, self.longitude, past)

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    @override_settings(TIME_ZONE='America/Vancouver')
    def test_event_earlier_today_is_not_refetched_in_a_western_timezone(self):
        # Arrange
        now = _local_hour_today(23)
        starts_at = now - timedelta(hours=14)
        ends_at = starts_at + timedelta(hours=2)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(
                    self.latitude, self.longitude, starts_at, ends_at
                )

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    @override_settings(TIME_ZONE='America/Vancouver')
    def test_event_from_the_previous_local_day_returns_none_in_a_western_timezone(self):
        # Arrange
        now = _local_hour_today(23)
        starts_at = now - timedelta(hours=25)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(
                    self.latitude, self.longitude, starts_at, starts_at + timedelta(hours=2)
                )

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_hourly_readings_are_stored_in_utc(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, window_end)

            # Act
            forecast = self.service.refresh_forecast(
                self.latitude, self.longitude, self.starts_at, window_end
            )

        # Assert
        times = [datetime.fromisoformat(entry['time']) for entry in forecast.hourly]
        self.assertEqual(times, [self.starts_at, window_end])
        for time in times:
            self.assertEqual(time.utcoffset(), timedelta(0))

    def test_requests_forecasts_in_utc(self):
        # Arrange
        window_end = self.starts_at + timedelta(hours=1)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, window_end)

            # Act
            self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at, window_end)

        # Assert
        for call in mock_get.call_args_list:
            self.assertEqual(call.kwargs['params']['timezone'], 'UTC')

    def test_event_that_started_before_midnight_returns_none(self):
        # Arrange
        now = _local_hour_today(3)
        starts_at = now - timedelta(hours=4)

        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            with patch('backoffice.services.forecast_service.requests.get') as mock_get:
                # Act
                forecast = self.service.refresh_forecast(
                    self.latitude, self.longitude, starts_at, starts_at + timedelta(hours=6)
                )

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_event_beyond_window_returns_none(self):
        # Arrange
        far_future = timezone.now() + timedelta(days=9)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, far_future)

        # Assert
        self.assertIsNone(forecast)
        mock_get.assert_not_called()

    def test_fetch_failure_leaves_the_previous_forecast_untouched(self):
        # Arrange
        stale = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.starts_at + timedelta(hours=1),
            hourly=_hourly_entry(self.starts_at, condition='cloud'),
        )
        Forecast.objects.filter(pk=stale.pk).update(
            prepared_at=timezone.now() - timedelta(hours=7)
        )

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError('boom')

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertIsNone(forecast)
        self.assertEqual(Forecast.objects.count(), 1)
        self.assertIsNone(
            self.service.get_forecast(self.starts_at)
        )

    def test_fetch_failure_without_stored_forecast_returns_none(self):
        # Arrange
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError('boom')

            # Act
            forecast = self.service.refresh_forecast(self.latitude, self.longitude, self.starts_at)

        # Assert
        self.assertIsNone(forecast)

    def test_condition_mapping_from_weather_codes(self):
        # Arrange
        expectations = {
            0: Forecast.Condition.SUN,
            1: Forecast.Condition.SUN,
            2: Forecast.Condition.CLOUD,
            45: Forecast.Condition.CLOUD,
            51: Forecast.Condition.RAIN,
            61: Forecast.Condition.RAIN,
            82: Forecast.Condition.RAIN,
            71: Forecast.Condition.SNOW,
            75: Forecast.Condition.SNOW,
            77: Forecast.Condition.SNOW,
            85: Forecast.Condition.SNOW,
            86: Forecast.Condition.SNOW,
            95: Forecast.Condition.THUNDER,
            99: Forecast.Condition.THUNDER,
        }

        for code, expected in expectations.items():
            # Act
            result = ForecastService._condition_from_weather_code(code)

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

    def test_missing_pollutant_data_still_produces_forecast_without_aqhi(self):
        # Arrange
        service = ForecastService()
        latitude, longitude = YOW_LOCATION
        starts_at = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        window_end = starts_at + timedelta(hours=1)

        def side_effect(url, **kwargs):
            if url == WEATHER_URL:
                return _mock_response(_weather_payload(starts_at, window_end))
            payload = _air_quality_payload(starts_at, window_end)
            hour_count = len(payload['hourly']['time'])
            payload['hourly']['pm2_5'] = [None] * hour_count
            payload['hourly']['nitrogen_dioxide'] = [None] * hour_count
            payload['hourly']['ozone'] = [None] * hour_count
            return _mock_response(payload)

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = side_effect

            # Act
            forecast = service.refresh_forecast(latitude, longitude, starts_at)

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(len(forecast.hourly), 2)
        self.assertTrue(all(entry['aqhi'] is None for entry in forecast.hourly))
        self.assertEqual(Forecast.objects.count(), 1)


class ForecastServiceWindowsTestCase(TestCase):
    def setUp(self):
        self.service = ForecastService()
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )

    def test_windows_sharing_an_hour_trigger_single_fetch(self):
        # Arrange
        first = (self.starts_at + timedelta(minutes=1), self.starts_at + timedelta(hours=1, minutes=1))
        second = (self.starts_at + timedelta(minutes=55), self.starts_at + timedelta(hours=1, minutes=55))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=2))

            # Act
            forecasts = self.service.refresh_forecasts_for_windows([first, second])

        # Assert
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(forecasts[first].pk, forecasts[second].pk)

    def test_windows_with_different_durations_get_separate_forecasts(self):
        # Arrange
        short = (self.starts_at, self.starts_at + timedelta(hours=1))
        long = (self.starts_at, self.starts_at + timedelta(hours=4))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            mock_get.side_effect = _mock_get(self.starts_at, self.starts_at + timedelta(hours=4))

            # Act
            forecasts = self.service.refresh_forecasts_for_windows([short, long])

        # Assert
        self.assertNotEqual(forecasts[short].pk, forecasts[long].pk)

    def test_window_outside_forecast_range_maps_to_none(self):
        # Arrange
        far_out = timezone.now() + timedelta(days=9)
        window = (far_out, far_out + timedelta(hours=1))

        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            # Act
            forecasts = self.service.refresh_forecasts_for_windows([window])

        # Assert
        self.assertIsNone(forecasts[window])
        mock_get.assert_not_called()

    def test_empty_windows_returns_empty_dict(self):
        # Act
        forecasts = self.service.refresh_forecasts_for_windows([])

        # Assert
        self.assertEqual(forecasts, {})


class ForecastServiceHistoryTestCase(TestCase):
    def setUp(self):
        self.service = ForecastService()
        self.latitude, self.longitude = YOW_LOCATION
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )

    def _create_forecast(self, start_time=None, end_time=None):
        start_time = start_time or self.starts_at
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=start_time,
            end_time=end_time or start_time + timedelta(hours=1),
            hourly=_hourly_entry(start_time, condition='sun'),
        )

    def test_returns_all_forecasts_for_window_newest_first(self):
        # Arrange
        older = self._create_forecast()
        Forecast.objects.filter(pk=older.pk).update(
            prepared_at=timezone.now() - timedelta(minutes=30)
        )
        newer = self._create_forecast()

        # Act
        forecasts = list(self.service.get_forecast_history(self.latitude, self.longitude, self.starts_at))

        # Assert
        self.assertEqual(forecasts, [newer, older])

    def test_excludes_forecasts_for_different_window(self):
        # Arrange
        self._create_forecast(start_time=self.starts_at + timedelta(days=1))

        # Act
        forecasts = list(self.service.get_forecast_history(self.latitude, self.longitude, self.starts_at))

        # Assert
        self.assertEqual(forecasts, [])

    def test_excludes_forecasts_without_hourly_readings(self):
        # Arrange
        with_readings = self._create_forecast()
        empty = self._create_forecast()
        Forecast.objects.filter(pk=empty.pk).update(hourly=[])

        # Act
        forecasts = list(self.service.get_forecast_history(self.latitude, self.longitude, self.starts_at))

        # Assert
        self.assertEqual(forecasts, [with_readings])

    def test_missing_end_defaults_to_one_hour_window(self):
        # Arrange
        self._create_forecast(end_time=self.starts_at + timedelta(hours=1))

        # Act
        forecasts = list(self.service.get_forecast_history(self.latitude, self.longitude, self.starts_at))

        # Assert
        self.assertEqual(len(forecasts), 1)
