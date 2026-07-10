import logging

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from waffle import flag_is_active

from backoffice.models import Event, Registration
from backoffice.services.membership_service import MembershipService
from backoffice.services.registration_service import RegistrationService, RegistrationDetail, RegistrationResult
from backoffice.services.request_service import RequestService
from backoffice.services.user_service import UserDetail, UserService
from web.forms import RegistrationForm, MembershipNumberForm, bool_to_yes_no

logger = logging.getLogger(__name__)


def registration_submitted(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/submitted.html')


def registration_verification_sent(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/verification_sent.html')


def registration_verify(request: HttpRequest) -> HttpResponse:
    token = request.GET.get('token')
    if not token:
        return render(request, 'web/registrations/verification_failed.html', {'reason': 'invalid'})

    service = RegistrationService()
    registration, error = service.verify_registration(token)

    if error:
        return render(request, 'web/registrations/verification_failed.html', {'reason': error})

    login(request, registration.user, backend='django.contrib.auth.backends.ModelBackend')
    return render(request, 'web/registrations/verification_success.html', {
        'registration': registration,
    })


CONTACT_FIELDS = ('first_name', 'last_name', 'email', 'phone')
EMERGENCY_CONTACT_FIELDS = ('emergency_contact_name', 'emergency_contact_phone')


def _is_section_collapsed(form: RegistrationForm, field_names: tuple, initial_data: dict) -> bool:
    if not all(initial_data.get(name) for name in field_names):
        return False
    if form.is_bound and any(name in form.errors for name in field_names):
        return False
    return True


def _get_registration_detail(form: RegistrationForm) -> RegistrationDetail:
    ride_leader_raw = form.cleaned_data.get('ride_leader_preference')
    first_time_raw = form.cleaned_data.get('first_time_attendee')
    return RegistrationDetail(
        ride=form.cleaned_data.get('ride'),
        speed_range_preference=form.cleaned_data.get('speed_range_preference'),
        emergency_contact_name=form.cleaned_data.get('emergency_contact_name'),
        emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone'),
        ride_leader_preference=bool_to_yes_no(ride_leader_raw, Registration.RideLeaderPreference)
        if 'ride_leader_preference' in form.cleaned_data else None,
        first_time_attendee=bool_to_yes_no(first_time_raw, Registration.FirstTimeAttendee)
        if 'first_time_attendee' in form.cleaned_data else None,
    )


def _get_user_details(form: RegistrationForm) -> UserDetail:
    return UserDetail(
        first_name=form.cleaned_data['first_name'],
        last_name=form.cleaned_data['last_name'],
        email=form.cleaned_data['email'],
        phone=form.cleaned_data['phone'],
        emergency_contact_name=form.cleaned_data.get('emergency_contact_name', ''),
        emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone', ''),
    )


def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    registration_service = RegistrationService()

    allowed, reason = registration_service.is_registration_allowed(event)
    if not allowed:
        logger.warning("Registration not allowed", extra={'event': event, 'reason': reason})
        return HttpResponseBadRequest(reason)

    # OK, proceed
    request_service = RequestService()
    user = request.user if request.user.is_authenticated else None

    initial_data = {}
    if user:
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.profile.phone,
            'emergency_contact_name': user.profile.emergency_contact_name,
            'emergency_contact_phone': user.profile.emergency_contact_phone,
        }

    speed_run = flag_is_active(request, 'registration_speed_run')

    form = RegistrationForm(request.POST or None, event=event, user=user, initial=initial_data)
    if not speed_run:
        form.order_fields([
            'first_name', 'last_name', 'email', 'phone',
            'ride', 'speed_range_preference',
            'emergency_contact_name', 'emergency_contact_phone',
        ])

    if request.method == 'POST':
        if form.is_valid():
            request_detail = request_service.extract_details(request)
            user_detail = _get_user_details(form)
            if user:
                user_detail.email = user.email
            result = registration_service.register(
                user_detail=user_detail,
                registration_detail=_get_registration_detail(form),
                event=event,
                request_detail=request_detail,
                acting_user=request.user if request.user.is_authenticated else None,
                force_verification=flag_is_active(request, 'require_email_verification'))

            if result == RegistrationResult.VERIFICATION_REQUIRED:
                return redirect('registration_verification_sent')

            if result == RegistrationResult.DUPLICATE:
                if request.user.is_authenticated:
                    return redirect('registration_submitted')
                return redirect('registration_verification_sent')

            if (flag_is_active(request, 'capture_membership_number')
                    and event.requires_membership):
                user_service = UserService()
                registered_user = user_service.find_by_email(user_detail.email).unwrap()
                membership_service = MembershipService()
                if request.user.is_authenticated and membership_service.has_current_membership_number(registered_user):
                    return redirect('registration_submitted')
                request.session['membership_capture_user_id'] = registered_user.id
                return redirect('membership_number_capture', event_id=event.id)

            return redirect('registration_submitted')

    # Determine the selected ride (if any) to pre-select speed ranges
    selected_ride_id = None

    if request.method == 'POST' and 'ride' in request.POST and request.POST['ride']:
        try:
            selected_ride_id = int(request.POST['ride'])
        except (ValueError, TypeError):
            pass

    return render(request, 'web/events/registration.html', {
        'event': event,
        'form': form,
        'selected_ride_id': selected_ride_id,
        'speed_run': speed_run,
        'contact_collapsed': speed_run and _is_section_collapsed(form, CONTACT_FIELDS, initial_data),
        'emergency_collapsed': (
            speed_run
            and 'emergency_contact_name' in form.fields
            and _is_section_collapsed(form, EMERGENCY_CONTACT_FIELDS, initial_data)
        ),
        'has_event_fields': any(
            name not in CONTACT_FIELDS + EMERGENCY_CONTACT_FIELDS for name in form.fields
        ),
    })


def membership_number_capture(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if not flag_is_active(request, 'capture_membership_number') or not event.requires_membership:
        return redirect('registration_submitted')

    user_id = request.session.get('membership_capture_user_id')

    if not user_id:
        return redirect('registration_submitted')

    if request.method == 'POST':
        # Skip button bypasses validation and cleans up session
        if 'skip' in request.POST:
            request.session.pop('membership_capture_user_id', None)
            return redirect('registration_submitted')

        form = MembershipNumberForm(request.POST)
        if form.is_valid():
            user = get_object_or_404(User, id=user_id)
            membership_service = MembershipService()
            if not membership_service.has_current_membership_number(user):
                membership_service.save_membership_number(user, form.cleaned_data['membership_number'])
            request.session.pop('membership_capture_user_id', None)
            return redirect('registration_submitted')
    else:
        form = MembershipNumberForm()

    return render(request, 'web/registrations/membership_number.html', {
        'event': event,
        'form': form,
    })
