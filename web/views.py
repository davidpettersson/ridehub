from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event
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


def registration_create(request: HttpRequest, event_id: int) -> HttpResponseRedirect | HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, event=event)
        if form.is_valid():
            registration = form.save()  # The save method now handles event assignment
            messages.success(request, "You've successfully registered for this event!")
            return redirect('event_detail', event_id=event.id)
    else:
        form = RegistrationForm(event=event)

    return render(request, 'web/events/register.html', {
        'event': event,
        'form': form,
    })

def registration_detail(request: HttpRequest, registration_id: int) -> HttpResponse:
    context = {}
    return render(request, 'web/registrations/detail.html')
