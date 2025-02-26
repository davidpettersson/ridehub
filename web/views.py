from django.shortcuts import render

from backoffice.models import Event


def calendar(request):
    context = {
        'events': Event.objects.all().order_by('starts_at')
    }
    return render(request, 'web/calendar.html', context)