from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Forecast


class ForecastModelTestCase(TestCase):
    def setUp(self):
        self.time = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)

    def _hourly(self, **overrides):
        entry = {
            'time': self.time.strftime('%Y-%m-%dT%H:%M'),
            'condition': 'sun',
            'temperature': 15,
            'aqhi': 3,
        }
        entry.update(overrides)
        return [entry]

    def _build_forecast(self, **overrides):
        fields = {
            'latitude': Decimal('45.32250'),
            'longitude': Decimal('-75.66920'),
            'start_time': self.time,
            'end_time': self.time + timedelta(hours=2),
            'hourly': self._hourly(),
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

    def test_empty_hourly_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=[])

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_hourly_entry_missing_keys_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=[{'time': self.time.strftime('%Y-%m-%dT%H:%M'), 'condition': 'sun'}])

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_hourly_entry_unknown_condition_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=self._hourly(condition='hail'))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_hourly_entry_aqhi_below_one_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=self._hourly(aqhi=0))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_hourly_entry_aqhi_above_eleven_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=self._hourly(aqhi=12))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_hourly_entry_invalid_time_rejected(self):
        # Arrange
        forecast = self._build_forecast(hourly=self._hourly(time='not-a-time'))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('hourly', ctx.exception.message_dict)

    def test_format_aqhi_caps_above_ten(self):
        # Act & Assert
        self.assertEqual(Forecast.format_aqhi(9), '9')
        self.assertEqual(Forecast.format_aqhi(11), '10+')

    def test_aqhi_category_for_mapping(self):
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

        for value, label in expectations.items():
            # Act & Assert
            self.assertEqual(Forecast.aqhi_category_for(value), label)
