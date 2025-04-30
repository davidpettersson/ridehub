import logging
from pprint import pprint
from secrets import token_urlsafe

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event, Registration, Ride
from backoffice.services import EmailService
from web.forms import RegistrationForm

logger = logging.getLogger(__name__)


def _split_full_name(name: str) -> tuple[str, str]:
    if ' ' in name:
        return tuple(name.split(' ', 1))
    else:
        return name, ''


def _absurd(msg: str = "Absurd!"):
    raise RuntimeError(msg)


def _create_or_update_user(form: RegistrationForm) -> User:
    name = form.cleaned_data['name']
    email = form.cleaned_data['email']

    users_with_email = User.objects.filter(email=email)
    assert users_with_email.count() <= 1

    first_name, last_name = _split_full_name(name)
    user = None

    match users_with_email.count():
        case 0:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=token_urlsafe(32),  # Random password
                first_name=first_name,
                last_name=last_name
            )
        case 1:
            user = users_with_email.first()
            user.first_name = first_name
            user.last_name = last_name
            user.save()
        case _:
            _absurd()

    return user


def _send_confirmation_email(host: str, registration: Registration) -> None:
    context = {
        'base_url': f"https://{host}",
        'registration': registration,
    }

    EmailService.send_email(
        template_name='confirmation',
        context=context,
        subject=f"Confirmed for {registration.event.name}",
        recipient_list=[registration.email],
    )

    registration.confirm()
    registration.save()


def _create_registration(event: Event, user: User, form: RegistrationForm) -> Registration:
    pprint(form.cleaned_data)
    registration = Registration()
    registration.event = event
    registration.user = user

    registration.name = form.cleaned_data['name']
    registration.email = form.cleaned_data['email']

    if event.has_rides:
        registration.ride = form.cleaned_data['ride']
        registration.speed_range_preference = form.cleaned_data['speed_range_preference']

    if event.ride_leaders_wanted:
        registration.ride_leader_preference = form.cleaned_data['ride_leader_preference']

    if event.requires_emergency_contact:
        registration.emergency_contact_name = form.cleaned_data['emergency_contact_name']
        registration.emergency_contact_phone = form.cleaned_data['emergency_contact_phone']

    registration.save()
    return registration


def registration_submitted(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/submitted.html', context={})


def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, event=event)
        if form.is_valid():
            user = _create_or_update_user(form)

            already_submitted_or_confirmed =\
                Registration.objects.filter(user=user, event=event, state__in=[Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED]).exists()

            if already_submitted_or_confirmed:
                # Do nothing, mostly because we don't want to reveal that they are registered already.
                # Log that a user attempted to register for an event they're already registered for.
                logger.info(
                    "User %s (%s) attempted to register for event %s (%s) but already has an active registration",
                    user.id, user.email, event.id, event.name
                )
            else:
                # OK, so either no registration exists, or it is withdrawn. Create a new one.
                registration = _create_registration(event, user, form)
                _send_confirmation_email(request.get_host(), registration)
            return redirect('registration_submitted')
    else:
        form = RegistrationForm(event=event)

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


@login_required
def registration_detail(request: HttpRequest, registration_id: int) -> HttpResponse:
    registration = get_object_or_404(Registration, id=registration_id)

    context = {
        'registration': registration,
    }
    return render(request, 'web/registrations/detail.html', context=context)


@login_required
def registration_list(request: HttpRequest) -> HttpResponse:
    context = {
        # 'registrations': Registration.objects.filter(user=request.user).order_by('event__starts_at'),
        'registrations': Registration.objects.all().order_by('event__starts_at'),
    }
    return render(request, 'web/registrations/list.html', context={})


def get_speed_ranges(request: HttpRequest, ride_id: int) -> HttpResponse:
    """HTMX endpoint to get speed ranges for a specific ride"""
    # Handle the case when no ride is selected (ride_id=0)
    if ride_id == 0:
        html = f'<select name="speed_range_preference" id="id_speed_range_preference" class="form-select" disabled>'
        html += '<option value="">Please select a ride first</option>'
        html += '</select>'
        return HttpResponse(html)

    ride = get_object_or_404(Ride, id=ride_id)
    speed_ranges = ride.speed_ranges.all()

    # Create a select element with the speed ranges
    html = f'<select name="speed_range_preference" id="id_speed_range_preference" class="form-select">'
    if not speed_ranges:
        html += '<option value="">No speed ranges available</option>'
    else:
        for speed_range in speed_ranges:
            html += f'<option value="{speed_range.id}">{speed_range}</option>'
    html += '</select>'

    return HttpResponse(html)
