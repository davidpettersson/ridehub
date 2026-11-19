from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Registration, Ride
from backoffice.services.event_service import EventService
from backoffice.services.forecast_summary import summarize
from backoffice.services.html_markdown import html_to_markdown

DEFAULT_WINDOW_MONTHS = 3
MAX_WINDOW_MONTHS = 12
MAX_QUERY_LENGTH = 100

REGISTRATION_ADVICE = (
    'Agents cannot register on behalf of a person. '
    'Registration must be completed by the person in a web browser.'
)
ARCHIVED_MESSAGE = 'This event has been archived and is no longer available.'


class AgentQueryError(ValueError):
    pass


@dataclass(frozen=True)
class EventWindow:
    start_date: date
    end_date: date


class AgentEventService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.event_service = EventService()

    def resolve_window(self, start_date: date | None, end_date: date | None,
                       today: date | None = None) -> EventWindow:
        today = today or timezone.localdate()
        start = start_date or today
        end = end_date or start + relativedelta(months=DEFAULT_WINDOW_MONTHS)
        if end < start:
            raise AgentQueryError('end_date must be on or after start_date.')
        if end > start + relativedelta(months=MAX_WINDOW_MONTHS):
            raise AgentQueryError(f'The date range cannot exceed {MAX_WINDOW_MONTHS} months.')
        return EventWindow(start_date=start, end_date=end)

    def list_events(self, start_date: date | None = None, end_date: date | None = None,
                    query: str | None = None, today: date | None = None) -> dict:
        window = self.resolve_window(start_date, end_date, today)
        query = (query or '').strip()
        if len(query) > MAX_QUERY_LENGTH:
            raise AgentQueryError(f'query cannot exceed {MAX_QUERY_LENGTH} characters.')
        events = self.event_service.fetch_events_between(window.start_date, window.end_date, query or None)
        return {
            'start_date': window.start_date.isoformat(),
            'end_date': window.end_date.isoformat(),
            'query': query or None,
            'count': len(events),
            'events': [self._summary(event) for event in events],
            'calendar_url': self._absolute(reverse('calendar')),
            'upcoming_url': self._absolute(reverse('upcoming')),
            'advice': (
                'Share each event url with the person so they can read more. '
                + REGISTRATION_ADVICE
            ),
        }

    def event_detail(self, event_id: int) -> dict:
        if event_id < 1:
            raise AgentQueryError('event_id must be a positive integer.')
        event = self._fetch_event(event_id)
        if event is None:
            raise AgentQueryError(f'No event with id {event_id} was found.')
        if event.archived:
            return {
                'id': event.id,
                'state': Event.STATE_ARCHIVED,
                'message': ARCHIVED_MESSAGE,
                'upcoming_url': self._absolute(reverse('upcoming')),
            }
        return self._detail(event)

    def _fetch_event(self, event_id: int) -> Event | None:
        rides = Ride.objects.select_related('route').prefetch_related('speed_ranges').annotate(
            confirmed_registration_count=Count(
                'registration',
                filter=Q(registration__state=Registration.STATE_CONFIRMED),
                distinct=True,
            )
        )
        return (
            Event.objects.select_related('program')
            .prefetch_related(Prefetch('ride_set', queryset=rides))
            .exclude(state=Event.STATE_DRAFT)
            .filter(id=event_id)
            .first()
        )

    def _summary(self, event: Event) -> dict:
        distance_range = event.distance_range
        return {
            'id': event.id,
            'name': event.name,
            'program': event.program.name,
            'state': event.state,
            'starts_at': self._timestamp(event.starts_at),
            'ends_at': self._timestamp(event.ends_at),
            'all_day': event.all_day,
            'location': event.location or None,
            'virtual': event.virtual,
            'ride_count': event.ride_count,
            'distance_km': (
                {'min': distance_range[0], 'max': distance_range[1]} if distance_range else None
            ),
            'participants': self._participants(event),
            'registration': self._registration(event),
            'url': self._event_url(event),
        }

    def _detail(self, event: Event) -> dict:
        detail = self._summary(event)
        detail.update({
            'description': html_to_markdown(event.description),
            'location_url': event.location_url or None,
            'requirements': {
                'membership_required': event.requires_membership,
                'emergency_contact_required': event.requires_emergency_contact,
            },
            'ride_leaders_wanted': event.ride_leaders_wanted,
            'rides': [self._ride(event, ride) for ride in event.ride_set.all()],
            'forecast': self._forecast(event),
            'cancellation': self._cancellation(event),
            'reschedule': self._reschedule(event),
        })
        return detail

    def _ride(self, event: Event, ride: Ride) -> dict:
        route = ride.route
        return {
            'name': ride.name,
            'description': html_to_markdown(ride.description) or None,
            'route': {
                'name': route.name,
                'url': route.url or None,
                'distance_km': route.distance or None,
                'elevation_gain_m': route.elevation_gain or None,
            },
            'speed_ranges': [speed_range.range for speed_range in ride.speed_ranges.all()],
            'participants': (
                ride.confirmed_registration_count if event.registrations_available else None
            ),
        }

    def _participants(self, event: Event) -> dict | None:
        if not event.registrations_available:
            return None
        return {
            'confirmed': event.registration_count,
            'limit': event.registration_limit,
            'spots_remaining': event.capacity_remaining,
        }

    def _registration(self, event: Event) -> dict:
        external = bool(event.external_registration_url)
        is_open = event.registration_open
        return {
            'open': is_open,
            'status': self._registration_status(event, is_open),
            'closes_at': self._timestamp(event.registration_closes_at),
            'external': external,
            'url': self._registration_url(event) if is_open else None,
            'how_to_register': self._how_to_register(event, is_open),
        }

    def _registration_status(self, event: Event, is_open: bool) -> str:
        if event.cancelled:
            return 'cancelled'
        if is_open:
            return 'open' if event.has_capacity_available else 'full'
        if not event.registration_enabled:
            return 'not_required'
        if event.state == Event.STATE_ANNOUNCED:
            return 'not_yet_open'
        return 'closed'

    def _how_to_register(self, event: Event, is_open: bool) -> str:
        if event.cancelled:
            return 'This event is cancelled; registration is not possible.'
        if is_open:
            return f'Open {self._registration_url(event)} in a web browser to register. {REGISTRATION_ADVICE}'
        return f'Registration is not open. Check {self._event_url(event)} in a web browser for updates.'

    def _registration_url(self, event: Event) -> str:
        if event.external_registration_url:
            return event.external_registration_url
        return self._absolute(reverse('registration_create', args=[event.id]))

    def _forecast(self, event: Event) -> dict | None:
        forecast = self.event_service.fetch_forecast(event)
        if forecast is None or not forecast.has_readings:
            return None
        summary = summarize(forecast)
        return {
            'summary': summary.aria_label,
            'prepared_at': self._timestamp(forecast.prepared_at),
            'hourly': [
                {
                    'time': self._timestamp(reading.time),
                    'condition': reading.condition.value,
                    'temperature_c': reading.temperature,
                    'aqhi': reading.aqhi_display,
                }
                for reading in summary.hourly
            ],
        }

    def _cancellation(self, event: Event) -> dict | None:
        if not event.cancelled:
            return None
        return {
            'cancelled_at': self._timestamp(event.cancelled_at),
            'reason': event.cancellation_reason or None,
        }

    def _reschedule(self, event: Event) -> dict | None:
        if not event.rescheduled_at:
            return None
        return {
            'rescheduled_at': self._timestamp(event.rescheduled_at),
            'previous_starts_at': self._timestamp(event.previous_starts_at),
            'reason': event.reschedule_reason or None,
        }

    def _event_url(self, event: Event) -> str:
        return self._absolute(reverse('event_detail', args=[event.id]))

    def _absolute(self, path: str) -> str:
        return f'{self.base_url}{path}'

    @staticmethod
    def _timestamp(value) -> str | None:
        if value is None:
            return None
        if timezone.is_naive(value):
            return value.isoformat()
        return timezone.localtime(value).isoformat()
