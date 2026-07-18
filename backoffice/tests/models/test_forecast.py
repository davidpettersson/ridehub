from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
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
            'time': self.time,
            'precipitation': Forecast.Precipitation.SUN,
            'temperature_min': 5,
            'temperature_max': 15,
            'aqhi': 3,
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
        forecast = self._build_forecast(time=self.time + timedelta(minutes=30))

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('time', ctx.exception.message_dict)

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

    def test_duplicate_location_and_time_rejected(self):
        # Arrange
        self._build_forecast().save()

        # Act & Assert
        with self.assertRaises(IntegrityError):
            self._build_forecast().save()

    def test_aqhi_below_one_rejected(self):
        # Arrange
        forecast = self._build_forecast(aqhi=0)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('aqhi', ctx.exception.message_dict)

    def test_aqhi_above_eleven_rejected(self):
        # Arrange
        forecast = self._build_forecast(aqhi=12)

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            forecast.full_clean()
        self.assertIn('aqhi', ctx.exception.message_dict)

    def test_aqhi_display_shows_value_up_to_ten(self):
        # Arrange
        forecast = self._build_forecast(aqhi=7)

        # Act & Assert
        self.assertEqual(forecast.aqhi_display, '7')

    def test_aqhi_display_caps_above_ten(self):
        # Arrange
        forecast = self._build_forecast(aqhi=11)

        # Act & Assert
        self.assertEqual(forecast.aqhi_display, '10+')

    def test_precipitation_emoji_mapping(self):
        # Arrange
        expectations = {
            Forecast.Precipitation.SUN: '☀️',
            Forecast.Precipitation.CLOUD: '☁️',
            Forecast.Precipitation.RAIN: '🌧️',
            Forecast.Precipitation.THUNDER: '⛈️',
        }

        for precipitation, emoji in expectations.items():
            # Act
            forecast = self._build_forecast(precipitation=precipitation)

            # Assert
            self.assertEqual(forecast.precipitation_emoji, emoji)
