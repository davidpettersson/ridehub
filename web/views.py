from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Event


def calendar(request: HttpRequest) -> HttpResponseRedirect:
    return redirect('event_list')

def event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event,
        id=event_id)

    context = {
        'event': event,
    }

    return render(request, 'web/event_detail.html', context)


def event_list(request: HttpRequest) -> HttpResponse:
    context = {
        'events': Event.objects.all().order_by('starts_at')
    }
    return render(request, 'web/event_list.html', context)
