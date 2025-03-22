from secrets import token_urlsafe

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event, Registration
from ridehub import settings
from web.forms import RegistrationForm


def redirect_to_event_list(request: HttpRequest) -> HttpResponseRedirect:
    return redirect('event_list')

def event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event,
        id=event_id)

    context = {
        'event': event,
    }

    return render(request, 'web/events/detail.html', context)


def event_list(request: HttpRequest) -> HttpResponse:
    context = {
        'events': Event.objects.all().order_by('starts_at')
    }
    return render(request, 'web/events/list.html', context)


def _split_full_name(name: str) -> tuple[str, str]:
    if ' ' in name:
        return tuple(name.split(' ', 1))
    else:
        return name, ''


def absurd(msg: str = "Absurd!"):
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
            absurd()

    return user


def _send_confirmation_email(registration: Registration) -> None:
    send_mail(
        from_email=f"Ottawa Bicycle Club <{settings.EMAIL_FROM}>",
        subject=f"[OBC] Confirmed for {registration.event.name}",
        message="You are confirmed for the event.",
        recipient_list=[registration.email],
    )

def _create_registration(event: Event, user: User, form: RegistrationForm) -> Registration:
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


def registration_confirmed(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/confirmed.html', context={})

def registration_already_exists(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/registrations/already_exists.html', context={})

def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, event=event)
        if form.is_valid():
            user = _create_or_update_user(form)
            if Registration.objects.filter(user=user, event=event).exists():
                return redirect('registration_already_exists')
            else:
                registration = _create_registration(event, user, form)
                _send_confirmation_email(registration)
                return redirect('registration_confirmed')
    else:
        form = RegistrationForm(event=event)

    return render(request, 'web/events/register.html', {
        'event': event,
        'form': form,
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
        #'registrations': Registration.objects.filter(user=request.user).order_by('event__starts_at'),
        'registrations': Registration.objects.all().order_by('event__starts_at'),
    }
    return render(request, 'web/registrations/list.html', context={})
