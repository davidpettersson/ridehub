from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Event


class EventService:
    def fetch_events(self, include_archived: bool = False, only_visible: bool = True) -> QuerySet[Event]:
        filters = {'archived': include_archived}

        if only_visible:
            filters['visible'] = True

        return Event.objects.filter(**filters).order_by('starts_at')

    def fetch_upcoming_events(self, include_archived: bool = False, only_visible: bool = True,
                              current_date: date | None = None) -> QuerySet[Event]:
        current_date = current_date or timezone.now().date()
        return self.fetch_events(include_archived, only_visible).filter(starts_at__date__gte=current_date)
