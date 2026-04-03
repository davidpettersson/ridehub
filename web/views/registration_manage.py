from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_tables2 import RequestConfig

from backoffice.models import Event, Registration
from backoffice.services.registration_service import RegistrationDetail, RegistrationService
from backoffice.services.user_service import UserDetail
from web.filters import RegistrationFilter
from web.forms import StaffRegistrationForm
from web.tables import RegistrationTable


def _require_staff(user):
    if not user.is_staff:
        raise PermissionDenied


@login_required
def event_registrations_manage(request: HttpRequest, event_id: int) -> HttpResponse:
    _require_staff(request.user)

    event = get_object_or_404(Event, id=event_id)

    if not event.registrations_available:
        registration_count = Registration.objects.filter(
            event_id=event_id,
            state__in=[Registration.STATE_CONFIRMED, Registration.STATE_UNVERIFIED],
        ).count()
        context = {
            'event': event,
            'registrations_available': False,
            'registration_count': registration_count,
        }
        return render(request, 'web/events/registrations_manage.html', context)

    registrations = Registration.objects.filter(
        event_id=event_id,
        state__in=[Registration.STATE_CONFIRMED, Registration.STATE_UNVERIFIED],
    ).select_related(
        'ride', 'speed_range_preference', 'user'
    ).order_by(
        'ride__ordering', 'speed_range_preference__lower_limit',
        'last_name', 'first_name'
    )

    registration_filter = RegistrationFilter(
        request.GET, queryset=registrations, event=event
    )

    table = RegistrationTable(registration_filter.qs)
    RequestConfig(request, paginate=False).configure(table)

    context = {
        'event': event,
        'table': table,
        'filter': registration_filter,
        'registrations_available': True,
    }

    return render(request, 'web/events/registrations_manage.html', context)


@login_required
def staff_registration_add(request: HttpRequest, event_id: int) -> HttpResponse:
    _require_staff(request.user)

    event = get_object_or_404(Event, id=event_id)

    if not event.registrations_available:
        return redirect('event_registrations_manage', event_id=event.id)

    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST, event=event)
        if form.is_valid():
            data = form.cleaned_data
            service = RegistrationService()

            user_detail = UserDetail(
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                phone=str(data['phone']),
                emergency_contact_name=data.get('emergency_contact_name', ''),
                emergency_contact_phone=data.get('emergency_contact_phone', ''),
            )

            registration_detail = RegistrationDetail(
                ride=data.get('ride'),
                ride_leader_preference=data.get('ride_leader_preference'),
                speed_range_preference=data.get('speed_range_preference'),
                emergency_contact_name=data.get('emergency_contact_name', ''),
                emergency_contact_phone=data.get('emergency_contact_phone', ''),
            )

            result = service.staff_register(user_detail, registration_detail, event, request.user)
            if result is None:
                form.add_error(None, "This person already has an active registration for this event.")
            else:
                return redirect('event_registrations_manage', event_id=event.id)
    else:
        form = StaffRegistrationForm(event=event)

    context = {
        'event': event,
        'form': form,
        'form_title': 'Add registration',
    }

    return render(request, 'web/events/registration_staff_form.html', context)


@login_required
def staff_registration_edit(request: HttpRequest, event_id: int, registration_id: int) -> HttpResponse:
    _require_staff(request.user)

    event = get_object_or_404(Event, id=event_id)

    if not event.registrations_available:
        return redirect('event_registrations_manage', event_id=event.id)

    registration = get_object_or_404(Registration, id=registration_id, event=event)

    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST, event=event)
        if form.is_valid():
            data = form.cleaned_data
            service = RegistrationService()

            fields = {
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'email': data['email'],
                'phone': str(data['phone']),
            }

            if 'ride' in data:
                fields['ride'] = data['ride']
            if 'speed_range_preference' in data:
                fields['speed_range_preference'] = data['speed_range_preference']
            if 'ride_leader_preference' in data:
                fields['ride_leader_preference'] = data['ride_leader_preference']
            if 'emergency_contact_name' in data:
                fields['emergency_contact_name'] = data['emergency_contact_name']
            if 'emergency_contact_phone' in data:
                fields['emergency_contact_phone'] = data['emergency_contact_phone']

            service.staff_update_registration(registration, **fields)
            return redirect('event_registrations_manage', event_id=event.id)
    else:
        initial = {
            'first_name': registration.first_name,
            'last_name': registration.last_name,
            'email': registration.email,
            'phone': registration.phone,
            'ride': registration.ride_id,
            'speed_range_preference': registration.speed_range_preference_id,
            'ride_leader_preference': registration.ride_leader_preference,
            'emergency_contact_name': registration.emergency_contact_name,
            'emergency_contact_phone': registration.emergency_contact_phone,
        }
        form = StaffRegistrationForm(initial=initial, event=event)

    context = {
        'event': event,
        'form': form,
        'form_title': 'Edit registration',
        'registration': registration,
    }

    return render(request, 'web/events/registration_staff_form.html', context)


@login_required
def staff_registration_withdraw(request: HttpRequest, event_id: int, registration_id: int) -> HttpResponse:
    _require_staff(request.user)

    if request.method != 'POST':
        return redirect('event_registrations_manage', event_id=event_id)

    event = get_object_or_404(Event, id=event_id)

    if not event.registrations_available:
        return redirect('event_registrations_manage', event_id=event.id)
    registration = get_object_or_404(Registration, id=registration_id, event=event)

    service = RegistrationService()
    service.staff_withdraw(registration, request.user)

    return redirect('event_registrations_manage', event_id=event.id)
