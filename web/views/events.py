import calendar
from datetime import datetime, date, timedelta
from itertools import groupby
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from django_tables2 import RequestConfig
from waffle import flag_is_active

from audit.services import AuditService
from backoffice.models import Event, Registration
from backoffice.services.event_service import EventService
from backoffice.services.forecast_service import ForecastService, YOW_LOCATION
from backoffice.services.registration_service import RegistrationService
from web.filters import PublicRegistrationFilter
from web.tables import PublicRegistrationTable


def _registrations_visible(event, user):
    if event.registrations_available:
        return True
    return user.is_authenticated and user.is_staff


def _is_confirmed_ride_leader(event_id, user):
    if not user.is_authenticated:
        return False
    return Registration.objects.filter(
        event_id=event_id,
        user=user,
        state=Registration.STATE_CONFIRMED,
        ride_leader_preference=Registration.RideLeaderPreference.YES
    ).exists()


def _viewer_can_see_all_names(event_id, user):
    if user.is_authenticated and user.is_staff:
        return True
    return _is_confirmed_ride_leader(event_id, user)


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


def _get_rides_with_riders_for_event(event_id: int, viewer) -> dict:
    event = get_object_or_404(Event, id=event_id)

    registrations = list(Registration.objects.filter(
        event_id=event_id,
        state=Registration.STATE_CONFIRMED
    ).select_related('ride', 'speed_range_preference', 'ride__route', 'user__profile'))

    RegistrationService().mask_hidden_names(
        registrations,
        viewer_is_authenticated=viewer.is_authenticated,
        viewer_is_privileged=_viewer_can_see_all_names(event_id, viewer),
    )

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

    if _registrations_visible(event, request.user):
        rides = _get_rides_with_riders_for_event(event_id, request.user)
    else:
        rides = {}

    user_is_registered = False
    if request.user.is_authenticated:
        user_is_registered = Registration.objects.filter(
            event_id=event_id,
            user=request.user,
            state=Registration.STATE_CONFIRMED,
        ).exists()

    forecast = None
    if flag_is_active(request, 'weather_forecast_badges') and event.has_rides:
        latitude, longitude = YOW_LOCATION
        forecast = ForecastService().get_forecast(latitude, longitude, event.starts_at)

    context = {
        'event': event,
        'rides': rides,
        'user_is_registered': user_is_registered,
        'registrations_available': _registrations_visible(event, request.user),
        'forecast': forecast,
    }

    return render(request, 'web/events/detail.html', context)


def _get_filter_params(request):
    if not flag_is_active(request, 'event_filter_and_search'):
        return False, '', ''

    active_query = request.GET.get('q', '').strip()
    filter_query_string = ('?' + urlencode({'q': active_query})) if active_query else ''
    return True, active_query, filter_query_string


def event_list(request: HttpRequest) -> HttpResponse:
    request.session['preferred_events_view'] = 'upcoming'

    filter_enabled, active_query, _ = _get_filter_params(request)

    events = list(EventService().fetch_upcoming_events(query=active_query))
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

    forecasts = {}
    if flag_is_active(request, 'weather_forecast_badges'):
        forecasts = ForecastService().get_forecasts_for_events(events)

    context = {
        'forecasts': forecasts,
        'events_by_date': events_by_date,
        'today': today,
        'tomorrow': tomorrow,
        'registered_event_ids': registered_event_ids,
        'filter_enabled': filter_enabled,
        'active_query': active_query,
    }

    if flag_is_active(request, 'upcoming_dense_view'):
        return render(request, 'web/events/list_dense.html', context)
    return render(request, 'web/events/list.html', context)


def _build_registrations_context(request, event, contacts_revealed):
    is_ride_leader = _is_confirmed_ride_leader(event.id, request.user)

    is_staff = request.user.is_authenticated and request.user.is_staff
    can_access_rider_contacts = is_ride_leader or is_staff
    can_reveal_contacts = can_access_rider_contacts

    all_riders = Registration.objects.filter(
        event_id=event.id,
        state=Registration.STATE_CONFIRMED
    ).select_related(
        'ride',
        'speed_range_preference',
        'user',
        'user__profile'
    ).order_by(
        'ride__ordering',
        'speed_range_preference__lower_limit',
        'user__first_name',
        'user__last_name'
    )

    registration_filter = PublicRegistrationFilter(
        request.GET, queryset=all_riders, event=event
    )

    filtered_riders = RegistrationService().mask_hidden_names(
        list(registration_filter.qs),
        viewer_is_authenticated=request.user.is_authenticated,
        viewer_is_privileged=can_access_rider_contacts,
    )

    contacts_hidden = can_reveal_contacts and not contacts_revealed
    exclude_columns = ()
    if not can_access_rider_contacts:
        exclude_columns = ('email', 'phone', 'emergency_contact_name', 'emergency_contact_phone', 'first_time_attendee')
    elif not event.ask_first_time_attendee:
        exclude_columns = ('first_time_attendee',)

    ride_counts = {}
    if can_access_rider_contacts:
        user_ids = [r.user_id for r in filtered_riders if r.user_id]
        ride_counts = RegistrationService().fetch_ride_counts(user_ids)

    table = PublicRegistrationTable(
        filtered_riders, exclude=exclude_columns,
        contacts_hidden=contacts_hidden, ride_counts=ride_counts,
    )
    RequestConfig(request, paginate=False).configure(table)

    return {
        'event': event,
        'all_riders': all_riders,
        'filtered_riders': filtered_riders,
        'table': table,
        'filter': registration_filter,
        'filter_clear_url': reverse('riders_list', args=[event.id]),
        'is_ride_leader': is_ride_leader,
        'can_access_rider_contacts': can_access_rider_contacts,
        'can_reveal_contacts': can_reveal_contacts,
        'contacts_revealed': contacts_revealed,
        'has_ride_leaders': any(
            rider.ride_leader_preference == Registration.RideLeaderPreference.YES
            for rider in all_riders
        ),
        'registrations_available': True,
    }


def event_registrations(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if not _registrations_visible(event, request.user):
        context = {
            'event': event,
            'all_riders': Registration.objects.none(),
            'is_ride_leader': False,
            'can_access_rider_contacts': False,
            'can_reveal_contacts': False,
            'contacts_revealed': False,
            'registrations_available': False,
            'registration_count': event.registration_count,
        }
        return render(request, 'web/events/registrations.html', context=context)

    context = _build_registrations_context(request, event, contacts_revealed=False)
    return render(request, 'web/events/registrations.html', context=context)


@login_required
@never_cache
def event_emergency_contacts(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if not _registrations_visible(event, request.user):
        return redirect('riders_list', event_id=event_id)

    if not _is_confirmed_ride_leader(event_id, request.user) and not request.user.is_staff:
        raise PermissionDenied

    if not request.headers.get('HX-Request'):
        return redirect('riders_list', event_id=event_id)

    AuditService().log(request.user, 'emergency_contacts_revealed', target=event)

    context = _build_registrations_context(request, event, contacts_revealed=True)
    return render(request, 'web/events/_registrations_list.html', context=context)


@login_required
@never_cache
def event_registrations_print(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if not _registrations_visible(event, request.user):
        return redirect('riders_list', event_id=event_id)

    if not _is_confirmed_ride_leader(event_id, request.user) and not request.user.is_staff:
        raise PermissionDenied

    AuditService().log(request.user, 'printable_emergency_contacts_viewed', target=event)

    context = _build_registrations_context(request, event, contacts_revealed=True)
    return render(request, 'web/events/registrations_print.html', context=context)


@login_required
def event_emails(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if not _is_confirmed_ride_leader(event_id, request.user) and not request.user.is_staff:
        raise PermissionDenied

    ride_leaders_only = request.GET.get('type') == 'leaders'
    emails = RegistrationService().fetch_confirmed_emails(event, ride_leaders_only=ride_leaders_only)

    action = 'ride_leader_emails_copied' if ride_leaders_only else 'all_emails_copied'
    AuditService().log(request.user, action, target=event)
    return HttpResponse(', '.join(emails), content_type='text/plain')



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

    filter_enabled, active_query, filter_query_string = _get_filter_params(request)

    events = list(EventService().fetch_events_for_month(year, month, query=active_query))

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    events_by_date = {}
    for event in events:
        local_starts_at = timezone.localtime(event.starts_at)
        start_date = local_starts_at.date()
        if event.all_day and event.ends_at:
            local_ends_at = timezone.localtime(event.ends_at)
            end_date = local_ends_at.date()
            total = (end_date - start_date).days + 1
            for i, d in enumerate(
                start_date + timedelta(days=n) for n in range(total)
            ):
                if month_start <= d <= month_end:
                    if d not in events_by_date:
                        events_by_date[d] = []
                    events_by_date[d].append({"event": event, "day_index": i + 1, "total_days": total})
        else:
            if month_start <= start_date <= month_end:
                if start_date not in events_by_date:
                    events_by_date[start_date] = []
                events_by_date[start_date].append({"event": event, "day_index": None, "total_days": None})

    for d in events_by_date:
        events_by_date[d].sort(key=lambda e: (0 if e["event"].all_day else 1, e["event"].starts_at))

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
        'filter_enabled': filter_enabled,
        'active_query': active_query,
        'filter_query_string': filter_query_string,
    }

    return render(request, 'web/events/calendar.html', context)
