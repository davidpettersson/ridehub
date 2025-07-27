from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Event


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
