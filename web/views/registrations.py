import logging

from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from waffle import flag_is_active

from backoffice.models import Event
from backoffice.services.membership_service import MembershipService
from backoffice.services.registration_service import RegistrationService, RegistrationDetail
from backoffice.services.request_service import RequestService
from backoffice.services.user_service import UserDetail, UserService
from web.forms import RegistrationForm, MembershipNumberForm

logger = logging.getLogger(__name__)


def registration_submitted(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/submitted.html')


def _get_registration_detail(form: RegistrationForm) -> RegistrationDetail:
    return RegistrationDetail(
        ride=form.cleaned_data.get('ride'),
        speed_range_preference=form.cleaned_data.get('speed_range_preference'),
        emergency_contact_name=form.cleaned_data.get('emergency_contact_name'),
        emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone'),
        ride_leader_preference=form.cleaned_data.get('ride_leader_preference'),
    )


def _get_user_details(form: RegistrationForm) -> UserDetail:
    return UserDetail(
        first_name=form.cleaned_data['first_name'],
        last_name=form.cleaned_data['last_name'],
        email=form.cleaned_data['email'],
        phone=form.cleaned_data['phone'],
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
        }

    form = RegistrationForm(request.POST or None, event=event, initial=initial_data)

    if request.method == 'POST':
        if form.is_valid():
            request_detail = request_service.extract_details(request)
            user_detail = _get_user_details(form)
            registration_service.register(
                user_detail=user_detail,
                registration_detail=_get_registration_detail(form),
                event=event,
                request_detail=request_detail)

            if (flag_is_active(request, 'capture_membership_number')
                    and event.requires_membership):
                # Look up the user that register() created/found so we can
                # store their ID in the session for the interstitial page.
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
