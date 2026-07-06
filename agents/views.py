from django.http import HttpRequest, HttpResponse
from django.urls import reverse


def llms_txt(request: HttpRequest) -> HttpResponse:
    upcoming_url = request.build_absolute_uri(reverse('upcoming'))
    calendar_url = request.build_absolute_uri(reverse('calendar'))
    feed_url = request.build_absolute_uri(reverse('event_feed'))

    lines = [
        '# Ottawa Bicycle Club',
        '',
        '> Cycling event calendar and ride registration for the Ottawa Bicycle Club.',
        '',
        'Content on this site is for non-commercial usage only.',
        '',
        '## Events',
        '',
        f'- [Upcoming events]({upcoming_url}): list of upcoming rides and events',
        f'- [Event calendar]({calendar_url}): monthly calendar of events',
        f'- [iCalendar feed]({feed_url}): machine-readable feed of all published events',
        '',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')
