from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Forecast
from backoffice.services.forecast_summary import summarize


class ForecastSummaryTestCase(TestCase):
    def setUp(self):
        self.time = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)

    def _hour(self, offset, condition, temperature, aqhi):
        return {
            'time': (self.time + timedelta(hours=offset)).strftime('%Y-%m-%dT%H:%M'),
            'condition': condition,
            'temperature': temperature,
            'aqhi': aqhi,
        }

    def _build_forecast(self, hourly):
        return Forecast(
            latitude=Decimal('45.32250'),
            longitude=Decimal('-75.66920'),
            start_time=self.time,
            end_time=self.time + timedelta(hours=len(hourly) - 1),
            hourly=hourly,
        )

    def test_prevalent_condition_wins_by_hour_count(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'cloud', 15, 3),
            self._hour(1, 'cloud', 15, 3),
            self._hour(2, 'sun', 16, 3),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.condition_primary, Forecast.Condition.CLOUD)
        self.assertIsNone(summary.condition_warning)

    def test_mild_outlier_condition_does_not_warn(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'cloud', 15, 3),
            self._hour(1, 'cloud', 15, 3),
            self._hour(2, 'sun', 16, 3),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertIsNone(summary.condition_warning)

    def test_severe_minority_condition_warns(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 21, 2),
            self._hour(2, 'sun', 21, 2),
            self._hour(3, 'thunder', 20, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.condition_primary, Forecast.Condition.SUN)
        self.assertEqual(summary.condition_warning, Forecast.Condition.THUNDER)
        self.assertEqual(summary.condition_warning_label, 'thunderstorms')

    def test_tied_conditions_break_toward_more_severe(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'thunder', 20, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.condition_primary, Forecast.Condition.THUNDER)
        self.assertIsNone(summary.condition_warning)

    def test_temperature_collapses_within_two_degree_span(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 22, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.temperature_display, '21')
        self.assertEqual(summary.temperature_aria_label, '21 degrees Celsius')

    def test_temperature_rounds_odd_midpoint_up(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 21, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.temperature_display, '21')

    def test_temperature_shows_range_beyond_two_degree_span(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 15, 2),
            self._hour(1, 'sun', 22, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.temperature_display, '15–22')
        self.assertEqual(summary.temperature_aria_label, '15 to 22 degrees Celsius')

    def test_prevalent_aqhi_category_wins_by_hour_count(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 2),
            self._hour(2, 'sun', 20, 5),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aqhi_category, 'low')
        self.assertEqual(summary.aqhi_warning_category, 'moderate')

    def test_aqhi_bump_to_moderate_warns(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 2),
            self._hour(2, 'sun', 20, 5),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aqhi_warning_category, 'moderate')

    def test_no_aqhi_warning_when_all_hours_share_category(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 3),
            self._hour(2, 'sun', 20, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aqhi_category, 'low')
        self.assertIsNone(summary.aqhi_warning_category)

    def test_aqhi_spike_to_high_warns(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 2),
            self._hour(2, 'sun', 20, 8),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aqhi_category, 'low')
        self.assertEqual(summary.aqhi_warning_category, 'high')

    def test_aria_label_combines_all_segments_without_warnings(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'cloud', 20, 2),
            self._hour(1, 'cloud', 21, 2),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aria_label, 'Weather: cloudy, 21 degrees Celsius, air quality low')

    def test_aria_label_includes_warnings_when_present(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 2),
            self._hour(2, 'thunder', 20, 8),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(
            summary.aria_label,
            'Weather: sunny, thunderstorms possible, 20 degrees Celsius, air quality low, spike to high',
        )

    def test_hourly_readings_are_parsed_and_ordered_as_stored(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'rain', 18, 4),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(len(summary.hourly), 2)
        self.assertEqual(summary.hourly[0].condition, Forecast.Condition.SUN)
        self.assertEqual(summary.hourly[0].temperature, 20)
        self.assertEqual(summary.hourly[1].condition, Forecast.Condition.RAIN)
        self.assertEqual(summary.hourly[1].aqhi_category, 'moderate')
        self.assertEqual(summary.hourly[1].aqhi_display, '4')

    def test_aqhi_category_is_none_when_no_hour_has_data(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, None),
            self._hour(1, 'sun', 21, None),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertIsNone(summary.aqhi_category)
        self.assertIsNone(summary.aqhi_warning_category)

    def test_aqhi_category_derived_only_from_available_hours(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, 2),
            self._hour(1, 'sun', 20, 2),
            self._hour(2, 'sun', 20, None),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aqhi_category, 'low')

    def test_aria_label_omits_air_quality_when_unavailable(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'cloud', 20, None),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertEqual(summary.aria_label, 'Weather: cloudy, 20 degrees Celsius')

    def test_hourly_reading_exposes_null_aqhi(self):
        # Arrange
        forecast = self._build_forecast([
            self._hour(0, 'sun', 20, None),
        ])

        # Act
        summary = summarize(forecast)

        # Assert
        self.assertIsNone(summary.hourly[0].aqhi)
        self.assertIsNone(summary.hourly[0].aqhi_display)
        self.assertIsNone(summary.hourly[0].aqhi_category)
