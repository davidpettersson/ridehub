from unittest.mock import patch

from django.test import TestCase

from backoffice.tasks import (
    alert_unconfirmed_registrations,
    debug_ping,
    refresh_forecasts,
    remind_unconfirmed_registrations,
)


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

    def test_logs_a_summary_of_the_run(self):
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
            with self.assertLogs('backoffice.tasks', level='INFO') as logs:
                refresh_forecasts()

        # Assert
        self.assertIn('2 windows stored for 1 events', logs.output[0])

    def test_logs_and_stops_when_no_events_are_within_the_horizon(self):
        # Arrange
        with patch(
            'backoffice.services.event_service.EventService.fetch_events_within_forecast_horizon'
        ) as fetch_events, patch(
            'backoffice.services.event_service.EventService.refresh_forecasts'
        ) as refresh:
            fetch_events.return_value = []

            # Act
            with self.assertLogs('backoffice.tasks', level='INFO') as logs:
                result = refresh_forecasts()

        # Assert
        self.assertEqual(result, 0)
        refresh.assert_not_called()
        self.assertIn('nothing to refresh', logs.output[0])


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


class RemindUnconfirmedRegistrationsTaskTests(TestCase):

    def test_delegates_to_the_reminder_service(self):
        # Act
        with patch(
            'backoffice.services.registration_reminder_service.RegistrationReminderService.remind_unconfirmed_registrations'
        ) as remind:
            remind.return_value = 2
            result = remind_unconfirmed_registrations()

        # Assert
        self.assertEqual(result, 2)
        remind.assert_called_once()
