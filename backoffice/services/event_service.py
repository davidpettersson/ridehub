from datetime import date, datetime, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Event, Ride


class EventService:
    def fetch_events(self, include_archived: bool = False, only_visible: bool = True) -> QuerySet[Event]:
        filters = {}
        
        if not include_archived:
            filters['archived'] = False

        if only_visible:
            filters['visible'] = True

        return Event.objects.filter(**filters).order_by('starts_at')

    def fetch_upcoming_events(self, include_archived: bool = False, only_visible: bool = True,
                              current_date: date | None = None) -> QuerySet[Event]:
        current_date = current_date or timezone.now().date()
        return self.fetch_events(include_archived, only_visible).filter(starts_at__date__gte=current_date)

    def fetch_events_for_month(self, year: int, month: int, include_archived: bool = False, 
                               only_visible: bool = True) -> QuerySet[Event]:
        from datetime import date
        import calendar
        
        first_day = date(year, month, 1)
        _, last_day_of_month = calendar.monthrange(year, month)
        last_day = date(year, month, last_day_of_month)
        
        return self.fetch_events(include_archived, only_visible).filter(
            starts_at__date__gte=first_day,
            starts_at__date__lte=last_day
        )

    def duplicate_event(self, source_event: Event, new_name: str, new_date: date) -> Event:
        date_delta = new_date - source_event.starts_at.date()

        new_starts_at = source_event.starts_at + date_delta
        new_ends_at = source_event.ends_at + date_delta if source_event.ends_at else None
        new_registration_closes_at = (
            source_event.registration_closes_at + date_delta
            if source_event.registration_closes_at
            else None
        )

        new_event = Event.objects.create(
            program=source_event.program,
            name=new_name,
            visible=True,
            location=source_event.location,
            location_url=source_event.location_url,
            starts_at=new_starts_at,
            ends_at=new_ends_at,
            registration_closes_at=new_registration_closes_at,
            external_registration_url=source_event.external_registration_url,
            registration_limit=source_event.registration_limit,
            description=source_event.description,
            virtual=source_event.virtual,
            ride_leaders_wanted=source_event.ride_leaders_wanted,
            requires_emergency_contact=source_event.requires_emergency_contact,
            requires_membership=source_event.requires_membership,
            organizer_email=source_event.organizer_email,
        )

        self._copy_rides(source_event, new_event)

        return new_event

    def _copy_rides(self, source_event: Event, target_event: Event) -> None:
        for ride in source_event.ride_set.all():
            new_ride = Ride.objects.create(
                event=target_event,
                name=ride.name,
                description=ride.description,
                route=ride.route,
                ordering=ride.ordering,
            )
            new_ride.speed_ranges.set(ride.speed_ranges.all())
