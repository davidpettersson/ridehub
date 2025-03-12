from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event, Registration
from web.forms import RegistrationForm

def calendar(request: HttpRequest) -> HttpResponseRedirect:
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

def _populate_registration_record(event: Event, form: RegistrationForm) -> Registration:
    registration = Registration()
    registration.event = event

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

    return registration

def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, event=event)
        if form.is_valid():
            registration = _populate_registration_record(event, form)
            registration.save()
            return redirect('registration_detail', registration_id=registration.id)
    else:
        form = RegistrationForm(event=event)

    return render(request, 'web/events/register.html', {
        'event': event,
        'form': form,
    })

def registration_detail(request: HttpRequest, registration_id: int) -> HttpResponse:
    registration = get_object_or_404(Registration, id=registration_id)
    context = {
        'registration': registration,
    }
    return render(request, 'web/registrations/detail.html', context=context)
