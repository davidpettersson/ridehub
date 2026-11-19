import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridehub.settings')

django_application = get_asgi_application()

from agents.mcp_server import MCP_PATH, build_mcp_app
from agents.middleware import AgentTrackingAsgiMiddleware, HttpsRequiredAsgiMiddleware

mcp_application = build_mcp_app()
tracked_mcp_application = AgentTrackingAsgiMiddleware(HttpsRequiredAsgiMiddleware(mcp_application))


async def application(scope, receive, send):
    if scope['type'] == 'lifespan':
        await mcp_application(scope, receive, send)
    elif scope['type'] == 'http' and scope['path'] == MCP_PATH:
        await tracked_mcp_application(scope, receive, send)
    else:
        await django_application(scope, receive, send)
