from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect

from backoffice.models import Event, Registration
from backoffice.services.event_service import EventService


def redirect_to_event_list(request: HttpRequest) -> HttpResponseRedirect:
    return redirect('event_list')


def event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event,
        id=event_id)

    context = {
        'event': event,
    }

    return render(request, 'web/events/detail.html', context)


def event_list(request: HttpRequest) -> HttpResponse:
    # TODO: Because events is a Django result set we can probably do something smarter here
    events = EventService.fetch_upcoming_events()
    starts_at_date = lambda event: event.starts_at.date()

    events_by_date = [
        (date, list(events_on_date)) for date, events_on_date in groupby(events, key=starts_at_date)
    ]

    context = {
        'events_by_date': events_by_date
    }

    return render(request, 'web/events/list.html', context)


@login_required
def event_riders(request: HttpRequest, event_id: int) -> HttpResponse:
    # Check if user is registered as a ride leader for this event
    registration = get_object_or_404(
        Registration,
        event_id=event_id,
        user=request.user,
        state=Registration.STATE_CONFIRMED,
        ride_leader_preference=Registration.RIDE_LEADER_YES
    )

    # Ensure the event requires ride leaders
    event = registration.event
    if not event.ride_leaders_wanted:
        return redirect('profile')

    # Get all confirmed registrations for this event
    registrations = Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related('ride', 'speed_range_preference', 'user')

    # Group registrations by ride and speed preference
    rides_dict = {}
    for reg in registrations:
        if reg.ride:
            if reg.ride.id not in rides_dict:
                rides_dict[reg.ride.id] = {
                    'ride': reg.ride,
                    'speed_ranges': {}
                }

            speed_range_id = reg.speed_range_preference.id if reg.speed_range_preference else 'none'
            if speed_range_id not in rides_dict[reg.ride.id]['speed_ranges']:
                rides_dict[reg.ride.id]['speed_ranges'][speed_range_id] = {
                    'speed_range': reg.speed_range_preference,
                    'riders': []
                }

            rides_dict[reg.ride.id]['speed_ranges'][speed_range_id]['riders'].append(reg)

    context = {
        'event': event,
        'rides': rides_dict.values()
    }

    return render(request, 'web/events/riders.html', context=context)


@login_required
def event_registrations(request: HttpRequest, event_id: int) -> HttpResponse:
    # Check if user is staff
    if not request.user.is_staff:
        raise PermissionDenied("You must be a staff member to access this page.")
        
    event = get_object_or_404(Event, id=event_id)
    
    # Get all registrations for this event
    registrations = Registration.objects.filter(event_id=event_id).order_by('submitted_at')
    
    context = {
        'event': event,
        'registrations': registrations
    }
    
    return render(request, 'web/events/registrations.html', context)
