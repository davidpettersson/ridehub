from itertools import groupby
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from backoffice.models import Event, Registration


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


# More idiomatic Django group check
def group_required(group_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login_form')
            
            if request.user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied(f"You must be in the {group_name} group to access this page.")
        return wrapper
    return decorator


@login_required
@group_required('Ride Administrators')
def event_registrations(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    
    # Get all registrations for this event
    registrations = Registration.objects.filter(event_id=event_id).order_by('submitted_at')
    
    context = {
        'event': event,
        'registrations': registrations
    }
    
    return render(request, 'web/events/registrations.html', context)
