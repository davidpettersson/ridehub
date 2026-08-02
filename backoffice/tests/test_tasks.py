from unittest.mock import patch

from django.test import TestCase

from backoffice.tasks import alert_unconfirmed_registrations, debug_ping, refresh_forecasts


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


class RefreshForecastsTaskTests(TestCase):

    def test_refreshes_forecasts_for_events_within_the_horizon(self):
        # Arrange
        events = [object()]

        # Act
        with patch(
            'backoffice.services.event_service.EventService.fetch_events_within_forecast_horizon'
        ) as fetch_events, patch(
            'backoffice.services.event_service.EventService.refresh_forecasts'
        ) as refresh:
            fetch_events.return_value = events
            refresh.return_value = 2
            result = refresh_forecasts()

        # Assert
        self.assertEqual(result, 2)
        refresh.assert_called_once_with(events)


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
