from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Forecast
from backoffice.services.forecast_service import YOW_LOCATION
from backoffice.tasks import alert_unconfirmed_registrations, debug_ping, fetch_forecast


class DebugPingTaskTests(TestCase):

    def test_returns_the_message_it_was_given(self):
        # Act
        result = debug_ping('hello')

        # Assert
        self.assertEqual(result, 'hello')

    def test_defaults_to_ping(self):
        # Act
        result = debug_ping()

        # Assert
        self.assertEqual(result, 'ping')


class FetchForecastTaskTests(TestCase):

    def setUp(self):
        self.latitude, self.longitude = YOW_LOCATION
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.ends_at = self.starts_at + timedelta(hours=1)

    def test_stores_the_fetched_forecast_and_returns_its_id(self):
        # Arrange
        forecast = Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.ends_at,
            hourly=[{'time': self.starts_at.isoformat(), 'condition': 'sun', 'temperature': 20, 'aqhi': 3}],
        )

        # Act
        with patch('backoffice.services.forecast_service.ForecastService.get_forecast') as get_forecast:
            get_forecast.return_value = forecast
            result = fetch_forecast(
                str(self.latitude), str(self.longitude),
                self.starts_at.isoformat(), self.ends_at.isoformat(),
            )

        # Assert
        self.assertEqual(result, forecast.id)
        get_forecast.assert_called_once_with(
            self.latitude, self.longitude, self.starts_at, self.ends_at
        )

    def test_returns_none_when_no_forecast_is_available(self):
        # Act
        with patch('backoffice.services.forecast_service.ForecastService.get_forecast') as get_forecast:
            get_forecast.return_value = None
            result = fetch_forecast(
                str(self.latitude), str(self.longitude),
                self.starts_at.isoformat(), self.ends_at.isoformat(),
            )

        # Assert
        self.assertIsNone(result)


class AlertUnconfirmedRegistrationsTaskTests(TestCase):

    def test_delegates_to_the_alert_service(self):
        # Act
        with patch(
            'backoffice.services.registration_alert_service.RegistrationAlertService.alert_unconfirmed_registrations'
        ) as alert:
            alert.return_value = 3
            result = alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(result, 3)
        alert.assert_called_once()
