from datetime import date
from typing import Annotated, Any

from asgiref.sync import sync_to_async
from django.conf import settings
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from backoffice.services.agent_event_service import AgentEventService, AgentQueryError

MCP_PATH = '/mcp'

SERVER_INSTRUCTIONS = (
    'Read-only access to the Ottawa Bicycle Club ride calendar. '
    'Use fetch_events to find rides and events, then fetch_event for full details. '
    'Always share the event url with the person. '
    'Registration cannot be done through this server: direct the person to the '
    'registration link to register in a web browser.'
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

server = MCPServer(
    name='Ottawa Bicycle Club rides',
    instructions=SERVER_INSTRUCTIONS,
    website_url=f'https://{settings.WEB_HOST}',
)


def base_url_for(ctx: Context) -> str:
    headers = ctx.headers or {}
    host = headers.get('host')
    if not host:
        return f'https://{settings.WEB_HOST}'
    scheme = headers.get('x-forwarded-proto', 'https' if settings.IS_HEROKU_APP else 'http')
    return f'{scheme}://{host}'


FETCH_EVENTS_DESCRIPTION = (
    'List published Ottawa Bicycle Club rides and events in a date range, with participant counts '
    'and links to each event page. Registration happens in a web browser.'
)
FETCH_EVENT_DESCRIPTION = (
    'Get full details of one event: description, rides, routes, speed ranges, participant counts, '
    'weather forecast and registration status. Participant names are never shared. '
    'Registration happens in a web browser.'
)


@server.tool(title='Fetch events', description=FETCH_EVENTS_DESCRIPTION, annotations=READ_ONLY, structured_output=True)
async def fetch_events(
    ctx: Context,
    start_date: Annotated[date | None, Field(description='First day to include (YYYY-MM-DD). Defaults to today.')] = None,
    end_date: Annotated[date | None, Field(description='Last day to include (YYYY-MM-DD). Defaults to three months after start_date. At most twelve months after start_date.')] = None,
    query: Annotated[str | None, Field(description='Optional text matched against event and program names.')] = None,
) -> dict[str, Any]:
    service = AgentEventService(base_url_for(ctx))
    try:
        return await sync_to_async(service.list_events)(start_date, end_date, query)
    except AgentQueryError as error:
        raise ToolError(str(error)) from error


@server.tool(title='Fetch event', description=FETCH_EVENT_DESCRIPTION, annotations=READ_ONLY, structured_output=True)
async def fetch_event(
    ctx: Context,
    event_id: Annotated[int, Field(description='The event id, as returned by fetch_events.')],
) -> dict[str, Any]:
    service = AgentEventService(base_url_for(ctx))
    try:
        return await sync_to_async(service.event_detail)(event_id)
    except AgentQueryError as error:
        raise ToolError(str(error)) from error


def transport_security() -> TransportSecuritySettings:
    if not settings.IS_HEROKU_APP:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=['127.0.0.1:*', 'localhost:*', '[::1]:*', '127.0.0.1', 'localhost', 'testserver'],
            allowed_origins=['http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*'],
        )
    hosts = [host for host in settings.ALLOWED_HOSTS if not host.startswith('.')]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=[f'https://{host}' for host in hosts],
    )


def build_mcp_app():
    return server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        transport_security=transport_security(),
    )
