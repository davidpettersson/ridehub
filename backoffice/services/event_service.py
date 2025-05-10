from django.db.models import QuerySet

from backoffice.models import Event
from django.utils import timezone


class EventService:
    def fetch_events(self, include_archived: bool=False) -> QuerySet[Event]:
        return Event.objects.filter(archived=include_archived).order_by('starts_at')

    def fetch_upcoming_events(self, include_archived: bool=False) -> QuerySet[Event]:
        return self.fetch_events(include_archived).filter(starts_at__gte=timezone.now())



