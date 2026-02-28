import calendar
from datetime import datetime, date, timedelta
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from waffle import flag_is_active

from backoffice.models import Event, Registration
from backoffice.services.event_service import EventService
from backoffice.services.registration_service import RegistrationService


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
    return sum(1 for r in riders if r.ride_leader_preference == Registration.RideLeaderPreference.YES)


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


def events_redirect(request: HttpRequest) -> HttpResponseRedirect:
    preferred_view = request.session.get('preferred_events_view', 'upcoming')

    if preferred_view == 'calendar':
        year = request.session.get('calendar_selected_year')
        month = request.session.get('calendar_selected_month')

        if year and month:
            return redirect('calendar_month', year=year, month=month)
        else:
            return redirect('calendar')
    else:
        return redirect('upcoming')


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
    # Set preferred view in session
    request.session['preferred_events_view'] = 'upcoming'

    events = list(EventService().fetch_upcoming_events())
    starts_at_date = lambda event: timezone.localtime(event.starts_at).date()

    events_by_date = [
        (date, list(events_on_date)) for date, events_on_date in groupby(events, key=starts_at_date)
    ]

    registered_event_ids = set()
    if request.user.is_authenticated:
        registered_event_ids = RegistrationService().fetch_confirmed_event_ids(
            request.user, [e.id for e in events]
        )

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    context = {
        'events_by_date': events_by_date,
        'today': today,
        'tomorrow': tomorrow,
        'registered_event_ids': registered_event_ids,
    }

    if flag_is_active(request, 'upcoming_dense_view'):
        return render(request, 'web/events/list_dense.html', context)
    return render(request, 'web/events/list.html', context)


def event_registrations(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    is_ride_leader = False

    if request.user.is_authenticated:
        is_ride_leader = Registration.objects.filter(
            event_id=event_id,
            user=request.user,
            state=Registration.STATE_CONFIRMED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        ).exists()

    can_access_rider_contacts = is_ride_leader or (request.user.is_authenticated and request.user.is_staff)

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

    all_emails = ', '.join(sorted(set(
        rider.email for rider in all_riders if rider.email
    )))

    ride_leader_emails = ', '.join(sorted(set(
        rider.email for rider in all_riders
        if rider.email and rider.ride_leader_preference == Registration.RideLeaderPreference.YES
    )))

    context = {
        'event': event,
        'all_riders': all_riders,
        'is_ride_leader': is_ride_leader,
        'can_access_rider_contacts': can_access_rider_contacts,
        'all_emails': all_emails,
        'ride_leader_emails': ride_leader_emails,
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


def calendar_view(request: HttpRequest, year: int = None, month: int = None) -> HttpResponse:
    request.session['preferred_events_view'] = 'calendar'

    if year is None or month is None:
        current_date = datetime.now()
        return redirect('calendar_month', year=current_date.year, month=current_date.month)

    current_year = datetime.now().year

    if not (1900 <= year <= current_year + 10):
        return redirect('calendar_month', year=current_year, month=datetime.now().month)

    if not (1 <= month <= 12):
        return redirect('calendar_month', year=current_year, month=datetime.now().month)

    request.session['calendar_selected_year'] = year
    request.session['calendar_selected_month'] = month

    events = list(EventService().fetch_events_for_month(year, month))

    events_by_date = {}
    for event in events:
        local_starts_at = timezone.localtime(event.starts_at)
        event_date = local_starts_at.date()
        if event_date not in events_by_date:
            events_by_date[event_date] = []
        events_by_date[event_date].append(event)

    registered_event_ids = set()
    if request.user.is_authenticated:
        registered_event_ids = RegistrationService().fetch_confirmed_event_ids(
            request.user, [e.id for e in events]
        )

    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    month_days = cal.monthdayscalendar(year, month)

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    context = {
        'current_date': date(year, month, 1),
        'month_name': calendar.month_abbr[month],
        'year': year,
        'month': month,
        'month_days': month_days,
        'events_by_date': events_by_date,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': date.today(),
        'registered_event_ids': registered_event_ids,
    }

    return render(request, 'web/events/calendar.html', context)
