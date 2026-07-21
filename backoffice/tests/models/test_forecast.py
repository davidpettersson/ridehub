from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Forecast


class ForecastModelTestCase(TestCase):
    def setUp(self):
        self.time = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)

    def _build_forecast(self, **overrides):
        fields = {
            'latitude': Decimal('45.32250'),
            'longitude': Decimal('-75.66920'),
            'start_time': self.time,
            'end_time': self.time + timedelta(hours=2),
            'conditions': 'sun',
            'temperature_min': 5,
            'temperature_max': 15,
            'aqhi_min': 3,
            'aqhi_max': 5,
        }
        fields.update(overrides)
        return Forecast(**fields)

    def test_valid_forecast_passes_validation(self):
        # Arrange
        forecast = self._build_forecast()

        # Act & Assert
        forecast.full_clean()

    def test_time_not_at_top_of_hour_rejected(self):
        # Arrange
        forecast = self._build_forecast(start_time=self.time + timedelta(minutes=30))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('start_time', ctx.exception.message_dict)

    def test_end_time_not_at_top_of_hour_rejected(self):
        # Arrange
        forecast = self._build_forecast(end_time=self.time + timedelta(hours=1, minutes=30))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('end_time', ctx.exception.message_dict)

    def test_end_time_before_time_rejected(self):
        # Arrange
        forecast = self._build_forecast(end_time=self.time - timedelta(hours=1))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('end_time', ctx.exception.message_dict)

    def test_temperature_min_above_max_rejected(self):
        # Arrange
        forecast = self._build_forecast(temperature_min=20, temperature_max=10)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('temperature_max', ctx.exception.message_dict)

    def test_latitude_out_of_range_rejected(self):
        # Arrange
        forecast = self._build_forecast(latitude=Decimal('91'))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('latitude', ctx.exception.message_dict)

    def test_longitude_out_of_range_rejected(self):
        # Arrange
        forecast = self._build_forecast(longitude=Decimal('-181'))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('longitude', ctx.exception.message_dict)

    def test_multiple_forecasts_allowed_for_same_location_and_window(self):
        # Arrange
        self._build_forecast().save()

        # Act
        self._build_forecast().save()

        # Assert
        self.assertEqual(Forecast.objects.count(), 2)

    def test_same_start_different_end_allowed(self):
        # Arrange
        self._build_forecast().save()

        # Act
        self._build_forecast(end_time=self.time + timedelta(hours=4)).save()

        # Assert
        self.assertEqual(Forecast.objects.count(), 2)

    def test_aqhi_below_one_rejected(self):
        # Arrange
        forecast = self._build_forecast(aqhi_min=0)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('aqhi_min', ctx.exception.message_dict)

    def test_aqhi_above_eleven_rejected(self):
        # Arrange
        forecast = self._build_forecast(aqhi_max=12)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('aqhi_max', ctx.exception.message_dict)

    def test_aqhi_min_above_max_rejected(self):
        # Arrange
        forecast = self._build_forecast(aqhi_min=7, aqhi_max=3)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('aqhi_max', ctx.exception.message_dict)

    def test_unknown_condition_category_rejected(self):
        # Arrange
        forecast = self._build_forecast(conditions='sun,hail')

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('conditions', ctx.exception.message_dict)

    def test_aqhi_worst_uses_max(self):
        # Arrange
        forecast = self._build_forecast(aqhi_min=3, aqhi_max=5)

        # Act & Assert
        self.assertEqual(forecast.aqhi_worst, 5)

    def test_aqhi_worst_display_caps_above_ten(self):
        # Arrange
        forecast = self._build_forecast(aqhi_min=9, aqhi_max=11)

        # Act & Assert
        self.assertEqual(forecast.aqhi_worst_display, '10+')

    def test_aqhi_category_label_mapping(self):
        # Arrange
        expectations = {
            1: 'low',
            3: 'low',
            4: 'moderate',
            6: 'moderate',
            7: 'high',
            10: 'high',
            11: 'very high',
        }

        for aqhi_max, label in expectations.items():
            # Act
            forecast = self._build_forecast(aqhi_min=1, aqhi_max=aqhi_max)

            # Assert
            self.assertEqual(forecast.aqhi_category_label, label)

    def test_temperature_display_collapses_equal_range(self):
        # Arrange
        forecast = self._build_forecast(temperature_min=12, temperature_max=12)

        # Act & Assert
        self.assertEqual(forecast.temperature_display, '12')

    def test_temperature_display_shows_range(self):
        # Arrange
        forecast = self._build_forecast(temperature_min=12, temperature_max=15)

        # Act & Assert
        self.assertEqual(forecast.temperature_display, '12\u201315')

    def test_condition_start_and_end_use_first_condition(self):
        # Arrange
        forecast = self._build_forecast(conditions='cloud,sun')

        # Act & Assert
        self.assertEqual(forecast.condition_start, Forecast.Condition.CLOUD)
        self.assertEqual(forecast.condition_end, Forecast.Condition.CLOUD)

    def test_condition_transition_aria_label_same_condition(self):
        # Arrange
        forecast = self._build_forecast(conditions='sun')

        # Act & Assert
        self.assertEqual(forecast.condition_transition_aria_label, 'sunny')

    def test_temperature_aria_label_collapses_equal_range(self):
        # Arrange
        forecast = self._build_forecast(temperature_min=21, temperature_max=21)

        # Act & Assert
        self.assertEqual(forecast.temperature_aria_label, '21 degrees Celsius')

    def test_temperature_aria_label_shows_range(self):
        # Arrange
        forecast = self._build_forecast(temperature_min=21, temperature_max=22)

        # Act & Assert
        self.assertEqual(forecast.temperature_aria_label, '21 to 22 degrees Celsius')

    def test_weather_aria_label_combines_all_segments(self):
        # Arrange
        forecast = self._build_forecast(conditions='cloud', temperature_min=21, temperature_max=22, aqhi_min=2, aqhi_max=3)

        # Act & Assert
        self.assertEqual(forecast.weather_aria_label, 'Weather: cloudy, 21 to 22 degrees Celsius, air quality low')
