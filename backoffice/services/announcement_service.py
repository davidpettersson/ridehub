from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Announcement


class AnnouncementService:
    def fetch_active_announcements(self, current_time=None) -> QuerySet[Announcement]:
        current_time = current_time or timezone.now()

        return Announcement.objects.filter(
            begin_at__lte=current_time,
            end_at__gte=current_time
        ).order_by('end_at')
