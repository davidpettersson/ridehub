from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from waffle.testutils import override_flag

from backoffice.models import Event, Forecast, Program, Ride, Route
from backoffice.services.forecast_service import YOW_LOCATION


class ForecastBadgeViewTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.route = Route.objects.create(name='Test Route')
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.latitude, self.longitude = YOW_LOCATION

    def _create_event(self, name='Test Event', starts_at=None, with_ride=True, virtual=False):
        starts_at = starts_at or self.starts_at
        event = Event.objects.create(
            program=self.program,
            name=name,
            description='Description',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            virtual=virtual,
        )
        if with_ride:
            Ride.objects.create(name=f'{name} ride', event=event, route=self.route)
        return event

    def _create_forecast(self, time=None, hourly=None):
        time = time or self.starts_at
        hourly = hourly or [
            {'time': time.strftime('%Y-%m-%dT%H:%M'), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            {'time': (time + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'), 'condition': 'cloud', 'temperature': 15, 'aqhi': 5},
        ]
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=time,
            end_time=time + timedelta(hours=1),
            hourly=hourly,
        )

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_badge_for_event_with_ride(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '12\u201315&nbsp;&deg;C')
        self.assertNotContains(response, '(beta)')
        self.assertNotContains(response, '\U0001F327')
        self.assertContains(response, 'Open-Meteo')

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_single_temperature_when_within_two_degree_span(self):
        # Arrange
        self._create_event()
        self._create_forecast(hourly=[
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            {'time': (self.starts_at + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
        ])

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, '12&nbsp;&deg;C')
        self.assertNotContains(response, '12\u201312')

    @override_flag('weather_forecast_badges', active=False)
    def test_upcoming_hides_badge_when_flag_disabled(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_badge_for_event_without_rides(self):
        # Arrange
        self._create_event(with_ride=False)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_hides_badge_for_virtual_event(self):
        # Arrange
        self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_badge_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_badge_for_event_with_ride(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '(beta)')

    @override_flag('weather_forecast_badges', active=False)
    def test_detail_hides_badge_when_flag_disabled(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_badge_for_event_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )
        event = self._create_event(starts_at=far_starts_at)

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_badge_for_cancelled_event(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()
        event.cancel()
        event.save()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
