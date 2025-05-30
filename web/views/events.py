from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect

from backoffice.models import Event, Registration
from backoffice.services.event_service import EventService


def _create_ride_structure(ride):
    return {
        'ride': ride,
        'speed_ranges': {
            str(sr.id): {
                'speed_range': sr,
                'riders': [],
                'sort_key': sr.lower_limit,
                'ride_leader_count': 0,
                'non_leader_count': 0
            }
            for sr in ride.speed_ranges.all()
        }
    }


def _initialize_rides_structure(event):
    return {
        str(ride.id): _create_ride_structure(ride)
        for ride in event.ride_set.all().prefetch_related('speed_ranges')
    }


def _get_speed_range_key(registration):
    return str(registration.speed_range_preference.id) if registration.speed_range_preference else 'none'


def _add_rider_to_speed_range(rides_data, ride_id, speed_range_key, registration):
    if speed_range_key == 'none':
        if 'none' not in rides_data[ride_id]['speed_ranges']:
            rides_data[ride_id]['speed_ranges']['none'] = {
                'speed_range': None,
                'riders': [],
                'sort_key': float('inf'),
                'ride_leader_count': 0,
                'non_leader_count': 0
            }
    
    rides_data[ride_id]['speed_ranges'][speed_range_key]['riders'].append(registration)


def _populate_riders(rides_data, registrations):
    for reg in registrations:
        if not reg.ride:
            continue
            
        ride_id = str(reg.ride.id)
        speed_range_key = _get_speed_range_key(reg)
        
        if speed_range_key in rides_data[ride_id]['speed_ranges'] or speed_range_key == 'none':
            _add_rider_to_speed_range(rides_data, ride_id, speed_range_key, reg)


def _count_ride_leaders(riders):
    return sum(1 for r in riders if r.ride_leader_preference == Registration.RIDE_LEADER_YES)


def _sort_speed_range_data(speed_ranges):
    sorted_items = sorted(
        speed_ranges.items(),
        key=lambda x: x[1]['sort_key']
    )
    
    sorted_speed_ranges = {}
    for speed_range_id, speed_range_data in sorted_items:
        speed_range_data['riders'].sort(key=lambda r: r.name)
        speed_range_data['ride_leader_count'] = _count_ride_leaders(speed_range_data['riders'])
        speed_range_data['non_leader_count'] = len(speed_range_data['riders']) - speed_range_data['ride_leader_count']
        sorted_speed_ranges[speed_range_id] = speed_range_data
    
    return sorted_speed_ranges


def _finalize_rides_data(rides_data):
    return {
        ride_id: {
            'ride': ride_info['ride'],
            'speed_ranges': _sort_speed_range_data(ride_info['speed_ranges'])
        }
        for ride_id, ride_info in rides_data.items()
    }


def _get_rides_with_riders_for_event(event_id: int) -> dict:
    event = get_object_or_404(Event, id=event_id)
    
    registrations = Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related('ride', 'speed_range_preference', 'ride__route')
    
    rides_data = _initialize_rides_structure(event)
    _populate_riders(rides_data, registrations)
    
    return _finalize_rides_data(rides_data)


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
        'rides': rides,  # Renamed from 'rides_with_riders'
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
