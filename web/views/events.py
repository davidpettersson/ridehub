from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect

from backoffice.models import Event, Registration
from backoffice.services.event_service import EventService


def _get_rides_with_riders_for_event(event_id: int) -> dict:
    """Fetches and structures registration data for an event."""
    event = get_object_or_404(Event, id=event_id)
    registrations = Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related('ride', 'speed_range_preference', 'ride__route')

    rides_with_riders = {}
    # Initialize with all rides and their speed ranges for the event
    for ride in event.ride_set.all().prefetch_related('speed_ranges'):
        ride_id_str = str(ride.id)
        rides_with_riders[ride_id_str] = {
            'ride': ride,
            'speed_ranges': {}
        }
        for sr in ride.speed_ranges.all():
            speed_range_id_str = str(sr.id)
            rides_with_riders[ride_id_str]['speed_ranges'][speed_range_id_str] = {
                'speed_range': sr,
                'riders': [],
                'sort_key': sr.lower_limit,
                'ride_leader_count': 0
            }

    # Populate riders into the structure
    for reg in registrations:
        if reg.ride:
            ride_id_str = str(reg.ride.id)
            # Ensure ride exists in our dict (it should, due to pre-population)
            if ride_id_str not in rides_with_riders:
                # This case should ideally not happen if rides are correctly pre-populated
                # but as a fallback, initialize it.
                rides_with_riders[ride_id_str] = {
                    'ride': reg.ride,
                    'speed_ranges': {}
                }

            speed_range_id_str = str(reg.speed_range_preference.id) if reg.speed_range_preference else 'none'

            # Ensure speed range exists in our dict for the ride
            if speed_range_id_str not in rides_with_riders[ride_id_str]['speed_ranges']:
                # This handles registrations with no speed preference or a preference not in the ride's defined ranges
                # For the purpose of displaying all defined speed ranges, we might not need to add it here
                # if it's 'none' or not a pre-defined one.
                # However, if it's a valid speed range that wasn't pre-populated (should not happen), initialize.
                if reg.speed_range_preference:  # Only add if there's an actual speed range preference
                    rides_with_riders[ride_id_str]['speed_ranges'][speed_range_id_str] = {
                        'speed_range': reg.speed_range_preference,
                        'riders': [],
                        'sort_key': reg.speed_range_preference.lower_limit,
                        'ride_leader_count': 0
                    }
                else:  # Case for 'none' or registrations without a speed range preference
                    if 'none' not in rides_with_riders[ride_id_str]['speed_ranges']:
                        rides_with_riders[ride_id_str]['speed_ranges']['none'] = {
                            'speed_range': None,  # Or some placeholder
                            'riders': [],
                            'sort_key': 0,  # Or appropriate sort key for 'none'
                            'ride_leader_count': 0
                        }
                    # Add rider to the 'none' category
                    rides_with_riders[ride_id_str]['speed_ranges']['none']['riders'].append(reg)
                    continue  # Skip to next registration as this one is handled

            # This check is crucial: only add rider if the speed_range_id_str is a key in pre-populated speed_ranges
            if speed_range_id_str in rides_with_riders[ride_id_str]['speed_ranges']:
                rides_with_riders[ride_id_str]['speed_ranges'][speed_range_id_str]['riders'].append(reg)

    # Sort speed ranges and riders, and count leaders
    for ride_id_str, ride_data in rides_with_riders.items():
        sorted_speed_ranges = {}
        # Sort pre-defined speed ranges
        # Filter out the 'none' key before sorting if it exists, handle it separately or ensure sort_key is appropriate

        # Correctly sort items, ensuring 'speed_range_data' is the value (x[1])
        # and 'sort_key' is accessed correctly from the nested dictionary.
        # Also, handle cases where 'speed_range' might be None (for 'none' category)
        sorted_items = sorted(
            ride_data['speed_ranges'].items(),
            key=lambda x: x[1]['sort_key'] if x[1]['speed_range'] else float('inf'),
            # Put 'none' last or handle as needed
            reverse=False
        )

        for speed_range_id_str, speed_range_data_val in sorted_items:
            speed_range_data_val['riders'].sort(key=lambda r: r.name)
            ride_leader_count = sum(
                1 for r in speed_range_data_val['riders'] if r.ride_leader_preference == Registration.RIDE_LEADER_YES)
            speed_range_data_val['ride_leader_count'] = ride_leader_count
            sorted_speed_ranges[speed_range_id_str] = speed_range_data_val
        rides_with_riders[ride_id_str]['speed_ranges'] = sorted_speed_ranges

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
