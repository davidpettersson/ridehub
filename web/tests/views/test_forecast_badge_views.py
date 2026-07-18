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

    def _create_event(self, name='Test Event', starts_at=None, with_ride=True):
        starts_at = starts_at or self.starts_at
        event = Event.objects.create(
            program=self.program,
            name=name,
            description='Description',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
        )
        if with_ride:
            Ride.objects.create(name=f'{name} ride', event=event, route=self.route)
        return event

    def _create_forecast(self, time=None):
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            time=time or self.starts_at,
            precipitation=Forecast.Precipitation.RAIN,
            temperature_min=12,
            temperature_max=15,
            aqi=5,
        )

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_shows_badge_for_event_with_ride(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQI&nbsp;5')
        self.assertContains(response, '12..15&nbsp;°C')
        self.assertContains(response, 'bi-cloud-rain')

    @override_flag('weather_forecast_badges', active=False)
    def test_upcoming_hides_badge_when_flag_disabled(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_upcoming_hides_badge_for_event_without_rides(self):
        # Arrange
        self._create_event(with_ride=False)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQI')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_shows_badge_for_event_with_ride(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQI&nbsp;5')

    @override_flag('weather_forecast_badges', active=False)
    def test_detail_hides_badge_when_flag_disabled(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQI')

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_badge_for_event_beyond_window(self):
        # Arrange
        far_starts_at = (timezone.now() + timedelta(days=6)).replace(
            minute=0, second=0, microsecond=0
        )
        event = self._create_event(starts_at=far_starts_at)

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQI')
        mock_get.assert_not_called()

    @override_flag('weather_forecast_badges', active=True)
    def test_detail_hides_badge_for_cancelled_event(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()
        event.cancel()
        event.save()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQI')
        mock_get.assert_not_called()
