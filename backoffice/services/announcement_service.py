from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Announcement


class AnnouncementService:
    def fetch_active_announcements(self, user, current_time=None) -> QuerySet[Announcement]:
        current_time = current_time or timezone.now()

        queryset = Announcement.objects.filter(
            begin_at__lte=current_time,
            end_at__gte=current_time
        )

        if user.is_authenticated:
            queryset = queryset.exclude(audience=Announcement.AUDIENCE_ANONYMOUS)
        else:
            queryset = queryset.exclude(audience=Announcement.AUDIENCE_SIGNED_IN)

        return queryset.order_by('end_at')
