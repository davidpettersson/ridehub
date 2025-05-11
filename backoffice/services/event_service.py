from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Event


class EventService:
    def fetch_events(self, include_archived: bool=False) -> QuerySet[Event]:
        return Event.objects.filter(archived=include_archived).order_by('starts_at')

    def fetch_upcoming_events(self, include_archived: bool=False) -> QuerySet[Event]:
        today = timezone.now().date()
        return self.fetch_events(include_archived).filter(starts_at__date__gte=today)



