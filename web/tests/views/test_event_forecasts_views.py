import json
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

    def test_returns_forecast_for_event_window(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['forecasts']), 1)
        forecast_data = data['forecasts'][0]
        self.assertEqual(forecast_data['conditions'], ['rain', 'cloud'])
        self.assertEqual(forecast_data['temperature_min'], 12)
        self.assertEqual(forecast_data['temperature_max'], 15)
        self.assertEqual(forecast_data['aqhi_min'], 5)
        self.assertEqual(forecast_data['aqhi_max'], 5)

    def test_returns_all_forecasts_prepared_for_window_newest_first(self):
        # Arrange
        event = self._create_event()
        older = self._create_forecast(
            conditions='sun', prepared_at=timezone.now() - timedelta(minutes=30)
        )
        newer = self._create_forecast(conditions='rain')

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        data = json.loads(response.content)
        prepared_ats = [f['prepared_at'] for f in data['forecasts']]
        self.assertEqual(len(data['forecasts']), 2)
        self.assertEqual(data['forecasts'][0]['prepared_at'], newer.prepared_at.isoformat())
        self.assertEqual(data['forecasts'][1]['prepared_at'], older.prepared_at.isoformat())
        self.assertEqual(prepared_ats, sorted(prepared_ats, reverse=True))

    def test_excludes_forecasts_for_other_windows(self):
        # Arrange
        event = self._create_event()
        self._create_forecast(start_time=self.starts_at + timedelta(days=1))

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        data = json.loads(response.content)
        self.assertEqual(data['forecasts'], [])

    def test_returns_empty_list_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        data = json.loads(response.content)
        self.assertEqual(data['forecasts'], [])

    def test_returns_empty_list_when_no_forecasts_prepared(self):
        # Arrange
        event = self._create_event()

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        data = json.loads(response.content)
        self.assertEqual(data['forecasts'], [])

    def test_uses_event_duration_to_determine_window(self):
        # Arrange
        event = self._create_event(ends_at=self.starts_at + timedelta(hours=3))
        self._create_forecast(end_time=self.starts_at + timedelta(hours=3))

        # Act
        response = self.client.get(reverse('event_forecasts', args=[event.id]))

        # Assert
        data = json.loads(response.content)
        self.assertEqual(len(data['forecasts']), 1)

    def test_returns_404_for_unknown_event(self):
        # Act
        response = self.client.get(reverse('event_forecasts', args=[999999]))

        # Assert
        self.assertEqual(response.status_code, 404)
