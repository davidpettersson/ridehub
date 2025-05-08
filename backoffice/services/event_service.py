from django.db.models import QuerySet

from backoffice.models import Event
from django.utils import timezone


class EventService:
    @classmethod
    def fetch_events(cls, include_archived: bool=False) -> QuerySet[Event]:
        return Event.objects.filter(archived=include_archived).order_by('starts_at')

    @classmethod
    def fetch_upcoming_events(cls, include_archived: bool=False) -> QuerySet[Event]:
        return cls.fetch_events(include_archived).filter(starts_at__gte=timezone.now())



