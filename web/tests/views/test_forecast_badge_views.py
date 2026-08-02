from datetime import timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Forecast, Program, Ride, Route
from backoffice.services.forecast_service import YOW_LOCATION


def _hour_label(time):
    return f"{int(time.strftime('%I'))} {time.strftime('%p')}"


def _hour_cell(time):
    return f"<td>{_hour_label(time)}</td>"


def _local_hour_today(hour):
    local = timezone.localtime(timezone.now()).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return local.astimezone(datetime_timezone.utc)


class ForecastBadgeTestCase(TestCase):
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
            {'time': time.isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 5},
            {'time': (time + timedelta(hours=1)).isoformat(), 'condition': 'cloud', 'temperature': 15, 'aqhi': 5},
        ]
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=time,
            end_time=time + timedelta(hours=1),
            hourly=hourly,
        )

    def _make_stale(self, forecast):
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=timezone.now() - timedelta(hours=7)
        )


class UpcomingPageForecastBadgeTests(ForecastBadgeTestCase):
    def test_upcoming_renders_badge_when_forecast_is_fresh(self):
        # Arrange
        self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '12–15&deg;')
        mock_get.assert_not_called()

    def test_upcoming_shows_no_badge_without_a_forecast(self):
        # Arrange
        self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    def test_upcoming_shows_no_badge_when_the_forecast_is_stale(self):
        # Arrange
        self._create_event()
        self._make_stale(self._create_forecast())

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    def test_upcoming_shows_no_badge_for_virtual_event(self):
        # Arrange
        self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')

    def test_upcoming_shows_no_badge_beyond_the_forecast_window(self):
        # Arrange
        starts_at = (timezone.now() + timedelta(days=9)).replace(
            minute=0, second=0, microsecond=0
        )
        self._create_event(starts_at=starts_at)
        self._create_forecast(time=starts_at)

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')

    def test_upcoming_renders_badge_for_ongoing_event(self):
        # Arrange
        now = _local_hour_today(12)
        starts_at = now - timedelta(hours=1)
        self._create_event(starts_at=starts_at)
        self._create_forecast(time=starts_at)

        # Act
        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')


class DetailPageForecastBadgeTests(ForecastBadgeTestCase):
    def test_detail_renders_badge_when_forecast_is_fresh(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')
        self.assertContains(response, '(beta)')
        self.assertContains(response, 'View forecast history')
        mock_get.assert_not_called()

    def test_detail_shows_no_badge_without_a_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        self.assertNotContains(response, 'View forecast history')
        mock_get.assert_not_called()

    def test_detail_shows_no_badge_when_the_forecast_is_stale(self):
        # Arrange
        event = self._create_event()
        self._make_stale(self._create_forecast())

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    def test_detail_shows_no_badge_for_virtual_event(self):
        # Arrange
        event = self._create_event(virtual=True)
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')

    def test_detail_keeps_the_badge_for_a_past_event(self):
        # Arrange
        starts_at = _local_hour_today(12) - timedelta(days=30)
        event = self._create_event(starts_at=starts_at)
        forecast = self._create_forecast(time=starts_at)
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=starts_at - timedelta(hours=2)
        )

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_detail_shows_no_badge_for_a_past_event_forecast_prepared_too_early(self):
        # Arrange
        starts_at = _local_hour_today(12) - timedelta(days=30)
        event = self._create_event(starts_at=starts_at)
        forecast = self._create_forecast(time=starts_at)
        Forecast.objects.filter(pk=forecast.pk).update(
            prepared_at=starts_at - timedelta(hours=8)
        )

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')

    def test_detail_renders_badge_for_event_finished_earlier_today(self):
        # Arrange
        now = _local_hour_today(20)
        starts_at = now - timedelta(hours=12)
        event = self._create_event(starts_at=starts_at)
        forecast = self._create_forecast(time=starts_at)
        Forecast.objects.filter(pk=forecast.pk).update(prepared_at=now - timedelta(hours=1))

        # Act
        with patch('backoffice.services.forecast_service.timezone.now', return_value=now):
            response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_detail_renders_badge_for_cancelled_event(self):
        # Arrange
        event = self._create_event()
        event.cancel()
        event.save()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_detail_renders_hourly_times_in_the_configured_timezone(self):
        # Arrange
        hour = self.starts_at.astimezone(datetime_timezone.utc).replace(hour=16)
        event = self._create_event(starts_at=hour)
        self._create_forecast(time=hour)

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, _hour_cell(timezone.localtime(hour)))
        self.assertNotContains(response, _hour_cell(hour))

    @override_settings(TIME_ZONE='America/Vancouver')
    def test_detail_renders_hourly_times_in_a_western_timezone(self):
        # Arrange
        hour = self.starts_at.astimezone(datetime_timezone.utc).replace(hour=16)
        event = self._create_event(starts_at=hour)
        self._create_forecast(time=hour)

        # Act
        response = self.client.get(reverse('event_detail', args=[event.id]))

        # Assert
        self.assertContains(response, _hour_cell(timezone.localtime(hour)))
        self.assertNotContains(response, _hour_cell(hour))


class RegistrationPagesForecastBadgeTests(ForecastBadgeTestCase):
    def test_registrations_renders_badge_when_forecast_is_fresh(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('riders_list', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_registrations_shows_no_badge_without_a_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('riders_list', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()

    def test_registration_form_renders_badge_when_forecast_is_fresh(self):
        # Arrange
        event = self._create_event()
        self._create_forecast()

        # Act
        response = self.client.get(reverse('registration_create', args=[event.id]))

        # Assert
        self.assertContains(response, 'AQHI&nbsp;moderate')

    def test_registration_form_shows_no_badge_without_a_forecast(self):
        # Arrange
        event = self._create_event()

        # Act
        with patch('backoffice.services.forecast_service.requests.get') as mock_get:
            response = self.client.get(reverse('registration_create', args=[event.id]))

        # Assert
        self.assertNotContains(response, 'AQHI&nbsp;moderate')
        mock_get.assert_not_called()
