from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect

from backoffice.models import Event, Registration, Ride
from backoffice.services.event_service import EventService


def _get_rides_with_riders_for_event(event_id: int) -> dict:
    """Fetches and structures registration data for an event, showing all speed ranges."""
    # First, get all rides for the event with their speed ranges
    rides = Ride.objects.filter(event_id=event_id).prefetch_related('speed_ranges')
    
    # Get all registrations for the event
    registrations = Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related('ride', 'speed_range_preference')
    
    # Build the structure with all speed ranges
    rides_with_riders = {}
    
    for ride in rides:
        ride_id = str(ride.id)
        rides_with_riders[ride_id] = {
            'ride': ride,
            'speed_ranges': {}
        }
        
        # Add all speed ranges for this ride
        for speed_range in ride.speed_ranges.all():
            speed_range_id = str(speed_range.id)
            rides_with_riders[ride_id]['speed_ranges'][speed_range_id] = {
                'speed_range': speed_range,
                'riders': [],
                'sort_key': speed_range.lower_limit,
                'ride_leader_count': 0
            }
    
    # Now populate with actual registrations
    for reg in registrations:
        if reg.ride:
            ride_id = str(reg.ride.id)
            if ride_id in rides_with_riders:
                speed_range_id = str(reg.speed_range_preference.id) if reg.speed_range_preference else 'none'
                
                # Handle case where someone has no speed range preference
                if speed_range_id == 'none' and speed_range_id not in rides_with_riders[ride_id]['speed_ranges']:
                    rides_with_riders[ride_id]['speed_ranges'][speed_range_id] = {
                        'speed_range': None,
                        'riders': [],
                        'sort_key': 0,
                        'ride_leader_count': 0
                    }
                
                if speed_range_id in rides_with_riders[ride_id]['speed_ranges']:
                    rides_with_riders[ride_id]['speed_ranges'][speed_range_id]['riders'].append(reg)
                    if reg.ride_leader_preference == Registration.RIDE_LEADER_YES:
                        rides_with_riders[ride_id]['speed_ranges'][speed_range_id]['ride_leader_count'] += 1

    # Sort speed ranges and riders
    for ride_id, ride_data in rides_with_riders.items():
        sorted_speed_ranges = {}
        for speed_range_id, speed_range_data in sorted(
            ride_data['speed_ranges'].items(),
            key=lambda x: x[1]['sort_key'],
            reverse=False
        ):
            speed_range_data['riders'].sort(key=lambda r: r.name)
            sorted_speed_ranges[speed_range_id] = speed_range_data
        rides_with_riders[ride_id]['speed_ranges'] = sorted_speed_ranges

    return rides_with_riders


def redirect_to_event_list(request: HttpRequest) -> HttpResponseRedirect:
    return redirect('event_list')


def event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event,
        id=event_id)

    rides = _get_rides_with_riders_for_event(event_id)
    
    user_is_registered = False
    if request.user.is_authenticated:
        user_is_registered = Registration.objects.filter(
            event_id=event_id,
            user=request.user,
            state=Registration.STATE_CONFIRMED
        ).exists()

    context = {
        'event': event,
        'rides': rides, # Renamed from 'rides_with_riders'
        'user_is_registered': user_is_registered,
    }

    return render(request, 'web/events/detail.html', context)


def event_list(request: HttpRequest) -> HttpResponse:
    events = EventService().fetch_upcoming_events()
    starts_at_date = lambda event: event.starts_at.date()

    events_by_date = [
        (date, list(events_on_date)) for date, events_on_date in groupby(events, key=starts_at_date)
    ]

    context = {
        'events_by_date': events_by_date
    }

    return render(request, 'web/events/list.html', context)


def event_registrations(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    
    is_ride_leader = False
    if request.user.is_authenticated:
        is_ride_leader = Registration.objects.filter(
            event_id=event_id,
            user=request.user,
            state=Registration.STATE_CONFIRMED,
            ride_leader_preference=Registration.RIDE_LEADER_YES
        ).exists()
    
    all_riders = Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related(
        'ride', 
        'speed_range_preference', 
        'user'
    ).order_by(
        'ride__ordering', 
        'speed_range_preference__lower_limit', 
        'user__first_name',
        'user__last_name'
    )

    context = {
        'event': event,
        'all_riders': all_riders,
        'is_ride_leader': is_ride_leader
    }

    return render(request, 'web/events/registrations.html', context=context)


@login_required
def event_registrations_full(request: HttpRequest, event_id: int) -> HttpResponse:
    if not request.user.is_staff:
        raise PermissionDenied("You must be a staff member to access this page.")

    event = get_object_or_404(Event, id=event_id)

    registrations = Registration.objects.filter(event_id=event_id).order_by('submitted_at')

    context = {
        'event': event,
        'registrations': registrations
    }

    return render(request, 'web/events/registrations_full.html', context)
