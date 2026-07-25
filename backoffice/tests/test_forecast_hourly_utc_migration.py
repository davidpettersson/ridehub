from datetime import datetime, timedelta
from decimal import Decimal
from importlib import import_module
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Forecast

migration = import_module('backoffice.migrations.0090_forecast_hourly_times_in_utc')


class ForecastHourlyUtcMigrationTestCase(TestCase):
    def setUp(self):
        self.start_time = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.provider_time = self.start_time.astimezone(ZoneInfo('America/Toronto'))

    def _create_forecast(self, hourly):
        return Forecast.objects.create(
            latitude=Decimal('45.32250'),
            longitude=Decimal('-75.66920'),
            start_time=self.start_time,
            end_time=self.start_time + timedelta(hours=1),
            hourly=hourly,
        )

    def _hourly(self, time):
        return [{'time': time, 'condition': 'sun', 'temperature': 15, 'aqhi': 3}]

    def test_converts_provider_local_times_to_utc(self):
        # Arrange
        forecast = self._create_forecast(
            self._hourly(self.provider_time.strftime('%Y-%m-%dT%H:%M'))
        )

        # Act
        migration.hourly_times_to_utc(apps, None)

        # Assert
        forecast.refresh_from_db()
        converted = datetime.fromisoformat(forecast.hourly[0]['time'])
        self.assertEqual(converted, self.start_time)
        self.assertEqual(converted.utcoffset(), timedelta(0))

    def test_leaves_readings_already_in_utc_untouched(self):
        # Arrange
        forecast = self._create_forecast(self._hourly(self.start_time.isoformat()))

        # Act
        migration.hourly_times_to_utc(apps, None)

        # Assert
        forecast.refresh_from_db()
        self.assertEqual(forecast.hourly[0]['time'], self.start_time.isoformat())

    def test_reverse_restores_provider_local_times(self):
        # Arrange
        forecast = self._create_forecast(self._hourly(self.start_time.isoformat()))

        # Act
        migration.hourly_times_to_provider_local(apps, None)

        # Assert
        forecast.refresh_from_db()
        self.assertEqual(
            forecast.hourly[0]['time'],
            self.provider_time.strftime('%Y-%m-%dT%H:%M'),
        )
