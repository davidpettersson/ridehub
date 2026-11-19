from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_safe

from agents.mcp_server import MCP_PATH

POPPY_PROTOCOL_VERSION = '1.0'
POPPY_CACHE_SECONDS = 60 * 60
ORGANIZATION_NAME = 'Ottawa Bicycle Club'
MCP_DESCRIPTION = (
    'Read-only ride calendar: list upcoming Ottawa Bicycle Club rides and events and get event details, '
    'including routes, participant counts and weather. Registration happens on the website in a web browser.'
)


def llms_txt(request: HttpRequest) -> HttpResponse:
    upcoming_url = request.build_absolute_uri(reverse('upcoming'))
    calendar_url = request.build_absolute_uri(reverse('calendar'))
    feed_url = request.build_absolute_uri(reverse('event_feed'))
    mcp_url = request.build_absolute_uri(MCP_PATH)
    poppy_url = request.build_absolute_uri(reverse('poppy_manifest'))

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
        '## Agents',
        '',
        f'- [MCP server]({mcp_url}): read-only tools fetch_events and fetch_event (Streamable HTTP)',
        f'- [Poppy manifest]({poppy_url}): Personal Agent Protocol discovery document',
        '',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@require_safe
def poppy_manifest(request: HttpRequest) -> JsonResponse:
    domain = request.get_host().lower()
    manifest = {
        'protocol_version': POPPY_PROTOCOL_VERSION,
        'organization': {
            'name': ORGANIZATION_NAME,
            'domain': domain,
        },
        'web': {},
        'apis': [
            {
                'type': 'mcp',
                'url': f'https://{domain}{MCP_PATH}',
                'description': MCP_DESCRIPTION,
            },
        ],
    }
    response = JsonResponse(manifest)
    patch_cache_control(response, public=True, max_age=POPPY_CACHE_SECONDS)
    return response
