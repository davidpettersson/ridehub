import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event, Registration
from backoffice.services.registration_service import RegistrationService, RegistrationDetail
from backoffice.services.user_service import UserDetail
from backoffice.utils import ensure
from web.forms import RegistrationForm

logger = logging.getLogger(__name__)


def _split_full_name(name: str) -> tuple[str, str]:
    if ' ' in name:
        return tuple(name.split(' ', 1))
    else:
        return name, ''


def registration_submitted(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/submitted.html', context={})


def _get_registration_detail(form: RegistrationForm) -> RegistrationDetail:
    return RegistrationDetail(
        ride=form.cleaned_data['ride'],
        speed_range_preference=form.cleaned_data['speed_range_preference'],
        emergency_contact_name=form.cleaned_data['emergency_contact_name'],
        emergency_contact_phone=form.cleaned_data['emergency_contact_phone'],
        ride_leader_preference=form.cleaned_data['ride_leader_preference'],
    )


def _get_user_details(form: RegistrationForm) -> UserDetail:
    first_name, last_name = _split_full_name(form.cleaned_data['name'])
    email = form.cleaned_data['email']
    return UserDetail(
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    service = RegistrationService()

    ensure(event.registration_open, 'registration is open')
    ensure(not event.cancelled, 'event must not be cancelled')
    ensure(not event.external_registration_url, 'event does not use external registration')

    user = request.user if request.user.is_authenticated else None

    initial_data = {}
    if user:
        initial_data = {
            'name': user.get_full_name(),
            'email': user.email,
        }

    form = RegistrationForm(request.POST or None, event=event, initial=initial_data)

    if request.method == 'POST':
        if form.is_valid():
            service.register(
                user_detail=_get_user_details(form),
                registration_detail=_get_registration_detail(form),
                event=event)
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
