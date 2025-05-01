from itertools import groupby
from pprint import pprint

from django.utils import timezone
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect

from backoffice.models import Event

def redirect_to_event_list(request: HttpRequest) -> HttpResponseRedirect:
    return redirect('event_list')


def event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event,
        id=event_id)

    context = {
        'event': event,
        'registration_closed': timezone.now() > event.registration_closes_at or event.is_cancelled,
    }

    return render(request, 'web/events/detail.html', context)


def event_list(request: HttpRequest) -> HttpResponse:
    events = Event.objects.all().order_by('starts_at')

    now = timezone.now()
    current_and_future_events = events.filter(starts_at__gte=now)

    def starts_at_date(event):
        return event.starts_at.date()

    events_by_date = []
    for date, events_on_date in groupby(current_and_future_events, key=starts_at_date):
        events_by_date.append((date, list(events_on_date)))

    context = {
        'events_by_date': events_by_date
    }

    return render(request, 'web/events/list.html', context)
