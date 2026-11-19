import datetime
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Forecast, Program, Registration, Ride, Route, SpeedRange
from backoffice.services.agent_event_service import AgentEventService, AgentQueryError
from backoffice.services.forecast_service import YOW_LOCATION

BASE_URL = 'https://obcrides.ca'


class BaseAgentEventServiceTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Social Rides')
        self.service = AgentEventService(BASE_URL)
        self.starts_at = (timezone.now() + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)

    def _create_event(self, name='Saturday Ride', state=Event.STATE_LIVE, starts_at=None, **kwargs):
        starts_at = starts_at or self.starts_at
        defaults = {
            'program': self.program,
            'name': name,
            'state': state,
            'description': '<p>Meet at the <strong>bridge</strong>.</p>',
            'starts_at': starts_at,
            'ends_at': starts_at + timedelta(hours=3),
            'registration_closes_at': starts_at - timedelta(hours=1),
            'location': 'Hog\'s Back Park',
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def _create_ride(self, event, name='A Ride', distance=80):
        route = Route.objects.create(name=f'{name} route', distance=distance, elevation_gain=500,
                                     url='https://ridewithgps.com/routes/1')
        ride = Ride.objects.create(name=name, event=event, route=route, description='<p>Fast pace</p>')
        ride.speed_ranges.add(SpeedRange.objects.create(lower_limit=28, upper_limit=32))
        return ride

    def _create_registration(self, event, ride=None, name='Jane Rider', state=Registration.STATE_CONFIRMED):
        return Registration.objects.create(
            event=event, ride=ride, name=name, email=f'{name.split()[0].lower()}@example.com', state=state,
        )


class ResolveWindowTestCase(BaseAgentEventServiceTestCase):
    def test_defaults_to_today_and_three_months_out(self):
        # Arrange
        today = datetime.date(2026, 11, 19)

        # Act
        window = self.service.resolve_window(None, None, today=today)

        # Assert
        self.assertEqual(window.start_date, today)
        self.assertEqual(window.end_date, datetime.date(2027, 2, 19))

    def test_end_defaults_relative_to_given_start(self):
        # Act
        window = self.service.resolve_window(datetime.date(2027, 1, 31), None)

        # Assert
        self.assertEqual(window.end_date, datetime.date(2027, 4, 30))

    def test_rejects_end_before_start(self):
        # Act / Assert
        with self.assertRaisesMessage(AgentQueryError, 'end_date must be on or after start_date'):
            self.service.resolve_window(datetime.date(2027, 2, 1), datetime.date(2027, 1, 1))

    def test_rejects_range_longer_than_twelve_months(self):
        # Act / Assert
        with self.assertRaisesMessage(AgentQueryError, 'cannot exceed 12 months'):
            self.service.resolve_window(datetime.date(2027, 1, 1), datetime.date(2028, 1, 2))

    def test_accepts_exactly_twelve_months(self):
        # Act
        window = self.service.resolve_window(datetime.date(2027, 1, 1), datetime.date(2028, 1, 1))

        # Assert
        self.assertEqual(window.end_date, datetime.date(2028, 1, 1))


class ListEventsTestCase(BaseAgentEventServiceTestCase):
    def test_lists_visible_events_in_window(self):
        # Arrange
        live = self._create_event('Live Ride')
        announced = self._create_event('Announced Ride', state=Event.STATE_ANNOUNCED)
        cancelled = self._create_event('Cancelled Ride', state=Event.STATE_CANCELLED)
        self._create_event('Draft Ride', state=Event.STATE_DRAFT)
        self._create_event('Archived Ride', state=Event.STATE_ARCHIVED)

        # Act
        result = self.service.list_events()

        # Assert
        ids = [event['id'] for event in result['events']]
        self.assertCountEqual(ids, [live.id, announced.id, cancelled.id])
        self.assertEqual(result['count'], 3)

    def test_excludes_events_outside_window(self):
        # Arrange
        self._create_event('Past Ride', starts_at=timezone.now() - timedelta(days=2))
        self._create_event('Far Ride', starts_at=timezone.now() + timedelta(days=200))
        inside = self._create_event('Soon Ride')

        # Act
        result = self.service.list_events()

        # Assert
        self.assertEqual([event['id'] for event in result['events']], [inside.id])

    def test_explicit_window_includes_past_events(self):
        # Arrange
        past_start = timezone.now() - timedelta(days=30)
        past = self._create_event('Past Ride', starts_at=past_start)

        # Act
        result = self.service.list_events(start_date=timezone.localdate(past_start) - timedelta(days=1),
                                          end_date=timezone.localdate())

        # Assert
        self.assertEqual([event['id'] for event in result['events']], [past.id])

    def test_filters_by_query_on_event_and_program_name(self):
        # Arrange
        gravel = self._create_event('Gravel Grinder')
        self._create_event('Road Ride')

        # Act
        result = self.service.list_events(query='gravel')

        # Assert
        self.assertEqual([event['id'] for event in result['events']], [gravel.id])

    def test_rejects_overlong_query(self):
        # Act / Assert
        with self.assertRaises(AgentQueryError):
            self.service.list_events(query='x' * 101)

    def test_summary_includes_links_counts_and_registration_advice(self):
        # Arrange
        event = self._create_event(registration_limit=10)
        ride = self._create_ride(event)
        self._create_registration(event, ride)
        self._create_registration(event, ride, name='Withdrawn Rider', state=Registration.STATE_WITHDRAWN)

        # Act
        summary = self.service.list_events()['events'][0]

        # Assert
        self.assertEqual(summary['url'], f'{BASE_URL}/events/{event.id}')
        self.assertEqual(summary['participants'], {'confirmed': 1, 'limit': 10, 'spots_remaining': 9})
        self.assertEqual(summary['distance_km'], {'min': 80, 'max': 80})
        self.assertEqual(summary['registration']['status'], 'open')
        self.assertEqual(summary['registration']['url'], f'{BASE_URL}/events/{event.id}/registration')
        self.assertIn('web browser', summary['registration']['how_to_register'])

    def test_result_never_contains_participant_names_or_emails(self):
        # Arrange
        event = self._create_event()
        self._create_registration(event, self._create_ride(event), name='Secret Person')

        # Act
        result = str(self.service.list_events())

        # Assert
        self.assertNotIn('Secret Person', result)
        self.assertNotIn('secret@example.com', result)


class EventDetailTestCase(BaseAgentEventServiceTestCase):
    def test_returns_rich_details(self):
        # Arrange
        event = self._create_event(requires_membership=True, location_url='https://maps.example.com/x')
        ride = self._create_ride(event)
        self._create_registration(event, ride)

        # Act
        detail = self.service.event_detail(event.id)

        # Assert
        self.assertEqual(detail['name'], 'Saturday Ride')
        self.assertEqual(detail['program'], 'Social Rides')
        self.assertEqual(detail['description'], 'Meet at the **bridge**.')
        self.assertEqual(detail['location_url'], 'https://maps.example.com/x')
        self.assertTrue(detail['requirements']['membership_required'])
        self.assertEqual(detail['rides'], [{
            'name': 'A Ride',
            'description': 'Fast pace',
            'route': {
                'name': 'A Ride route',
                'url': 'https://ridewithgps.com/routes/1',
                'distance_km': 80,
                'elevation_gain_m': 500,
            },
            'speed_ranges': ['28-32 km/h'],
            'participants': 1,
        }])
        self.assertIsNone(detail['cancellation'])

    def test_never_contains_participant_names_or_emails(self):
        # Arrange
        event = self._create_event()
        self._create_registration(event, self._create_ride(event), name='Secret Person')

        # Act
        detail = str(self.service.event_detail(event.id))

        # Assert
        self.assertNotIn('Secret Person', detail)
        self.assertNotIn('secret@example.com', detail)

    def test_uses_external_registration_url_when_set(self):
        # Arrange
        event = self._create_event(external_registration_url='https://tickets.example.com/ride')

        # Act
        registration = self.service.event_detail(event.id)['registration']

        # Assert
        self.assertTrue(registration['external'])
        self.assertEqual(registration['url'], 'https://tickets.example.com/ride')
        self.assertIn('https://tickets.example.com/ride', registration['how_to_register'])

    def test_announced_event_is_not_yet_open(self):
        # Arrange
        event = self._create_event(state=Event.STATE_ANNOUNCED)

        # Act
        registration = self.service.event_detail(event.id)['registration']

        # Assert
        self.assertFalse(registration['open'])
        self.assertEqual(registration['status'], 'not_yet_open')
        self.assertIsNone(registration['url'])
        self.assertIn(f'/events/{event.id}', registration['how_to_register'])

    def test_full_event_reports_full(self):
        # Arrange
        event = self._create_event(registration_limit=1)
        self._create_registration(event)

        # Act
        registration = self.service.event_detail(event.id)['registration']

        # Assert
        self.assertEqual(registration['status'], 'full')

    def test_cancelled_event_includes_reason(self):
        # Arrange
        event = self._create_event(state=Event.STATE_CANCELLED, cancelled_at=timezone.now(),
                                   cancellation_reason='Thunderstorms')

        # Act
        detail = self.service.event_detail(event.id)

        # Assert
        self.assertEqual(detail['registration']['status'], 'cancelled')
        self.assertEqual(detail['cancellation']['reason'], 'Thunderstorms')

    def test_rescheduled_event_includes_previous_start(self):
        # Arrange
        previous = self.starts_at - timedelta(days=1)
        event = self._create_event(rescheduled_at=timezone.now(), previous_starts_at=previous,
                                   reschedule_reason='Road closure')

        # Act
        reschedule = self.service.event_detail(event.id)['reschedule']

        # Assert
        self.assertEqual(reschedule['reason'], 'Road closure')
        self.assertEqual(reschedule['previous_starts_at'], timezone.localtime(previous).isoformat())

    def test_past_event_hides_counts_after_visibility_window(self):
        # Arrange
        starts_at = timezone.now() - timedelta(days=10)
        event = self._create_event(starts_at=starts_at)
        ride = self._create_ride(event)
        self._create_registration(event, ride)

        # Act
        detail = self.service.event_detail(event.id)

        # Assert
        self.assertEqual(detail['name'], 'Saturday Ride')
        self.assertIsNone(detail['participants'])
        self.assertIsNone(detail['rides'][0]['participants'])
        self.assertEqual(detail['registration']['status'], 'closed')

    def test_archived_event_returns_minimal_information(self):
        # Arrange
        event = self._create_event(state=Event.STATE_ARCHIVED)

        # Act
        detail = self.service.event_detail(event.id)

        # Assert
        self.assertEqual(detail, {
            'id': event.id,
            'state': 'archived',
            'message': 'This event has been archived and is no longer available.',
            'upcoming_url': f'{BASE_URL}/upcoming',
        })

    def test_draft_event_is_not_found(self):
        # Arrange
        event = self._create_event(state=Event.STATE_DRAFT)

        # Act / Assert
        with self.assertRaisesMessage(AgentQueryError, 'No event'):
            self.service.event_detail(event.id)

    def test_unknown_event_is_not_found(self):
        # Act / Assert
        with self.assertRaisesMessage(AgentQueryError, 'No event'):
            self.service.event_detail(999999)

    def test_rejects_non_positive_id(self):
        # Act / Assert
        with self.assertRaisesMessage(AgentQueryError, 'positive integer'):
            self.service.event_detail(0)

    def test_includes_forecast_when_available(self):
        # Arrange
        event = self._create_event(starts_at=timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1))
        latitude, longitude = YOW_LOCATION
        Forecast.objects.create(
            latitude=latitude,
            longitude=longitude,
            start_time=event.starts_at,
            end_time=event.ends_at,
            hourly=[{'time': event.starts_at.isoformat(), 'condition': 'rain', 'temperature': 12, 'aqhi': 3}],
        )

        # Act
        forecast = self.service.event_detail(event.id)['forecast']

        # Assert
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast['hourly'][0]['condition'], 'rain')
        self.assertEqual(forecast['hourly'][0]['temperature_c'], 12)
        self.assertTrue(forecast['summary'])

    def test_forecast_is_none_without_data(self):
        # Arrange
        event = self._create_event()

        # Act
        forecast = self.service.event_detail(event.id)['forecast']

        # Assert
        self.assertIsNone(forecast)
