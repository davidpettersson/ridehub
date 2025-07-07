from datetime import timedelta

from django.urls import reverse
from django_ical.views import ICalFeed

from backoffice.models import Event
from backoffice.services.event_service import EventService


class EventFeed(ICalFeed):
    product_id = '-//ridehub//RideHub//EN'
    timezone = 'America/Toronto'
    file_name = "event.ics"
    title = 'OBC Events'

    def items(self):
        return EventService().fetch_events()

    def item_title(self, item: Event):
        return item.name

    def item_description(self, item: Event):
        return item.description

    def item_start_datetime(self, item: Event):
        return item.starts_at

    def item_end_datetime(self, item: Event):
        if item.ends_at:
            return item.ends_at
        else:
            return item.starts_at + timedelta(hours=1)

    def item_link(self, item: Event):
        return reverse('event_detail', args=[item.id])

    def item_location(self, item: Event):
        if item.location_url:
            return item.location_url
        else:
            return item.location
