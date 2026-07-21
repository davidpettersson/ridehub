from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Forecast, Program
from backoffice.services.forecast_service import YOW_LOCATION


class EventForecastsViewTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.starts_at = (timezone.now() + timedelta(days=1)).replace(
            minute=0, second=0, microsecond=0
        )
        self.latitude, self.longitude = YOW_LOCATION

    def _create_event(self, starts_at=None, ends_at=None, virtual=False):
        starts_at = starts_at or self.starts_at
        return Event.objects.create(
            program=self.program,
            name='Test Event',
            description='Description',
            starts_at=starts_at,
            ends_at=ends_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            virtual=virtual,
        )

    def _create_forecast(self, start_time=None, end_time=None, prepared_at=None, **overrides):
        start_time = start_time or self.starts_at
        end_time = end_time or (start_time + timedelta(hours=1))
        fields = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_time': start_time,
            'end_time': end_time,
            'conditions': 'rain,cloud',
            'temperature_min': 12,
            'temperature_max': 15,
            'aqhi_min': 5,
            'aqhi_max': 5,
            **overrides,
        }
        forecast = Forecast.objects.create(**fields)
        if prepared_at:
            Forecast.objects.filter(pk=forecast.pk).update(prepared_at=prepared_at)
            forecast.refresh_from_db()
        return forecast

    def test_renders_forecast_for_event_window(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/forecasts.html')
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '12\u201315&nbsp;&deg;C')
        self.assertContains(response, 'rainy')

    def test_shows_all_forecasts_prepared_for_window_newest_first(self):
        # Arrange
        event = self._create_event()
        self._create_forecast(
            conditions='sun', prepared_at=timezone.now() - timedelta(minutes=30)
        )
        self._create_forecast(conditions='rain')

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        content = response.content.decode()
        self.assertContains(response, 'rainy')
        self.assertContains(response, 'sunny')
        self.assertLess(content.index('rainy'), content.index('sunny'))

    def test_excludes_forecasts_for_other_windows(self):
        # Arrange
        event = self._create_event()
        self._create_forecast(start_time=self.starts_at + timedelta(days=1))

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertContains(response, 'No forecasts have been prepared for this event yet.')

    def test_shows_empty_state_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertContains(response, 'No forecasts have been prepared for this event yet.')

    def test_shows_empty_state_when_no_forecasts_prepared(self):
        # Arrange
        event = self._create_event()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertContains(response, 'No forecasts have been prepared for this event yet.')

    def test_uses_event_duration_to_determine_window(self):
        # Arrange
        event = self._create_event(ends_at=self.starts_at + timedelta(hours=3))
        self._create_forecast(end_time=self.starts_at + timedelta(hours=3))

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_returns_404_for_unknown_event(self):
        # Act
        response = self.client.get(reverse('event_forecasts', args=[999999]))

        # Assert
        self.assertEqual(response.status_code, 404)

    def test_back_link_points_to_event_detail(self):
        # Arrange
        event = self._create_event()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertContains(response, reverse('event_detail', args=[event.id]))
