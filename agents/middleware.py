import logging

import sentry_sdk
from asgiref.sync import sync_to_async

from agents.models import AgentRequest
from agents.services import AgentDetectionService
from backoffice.services.request_service import RequestService

logger = logging.getLogger(__name__)


class AgentTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.detection_service = AgentDetectionService()
        self.request_service = RequestService()

    def __call__(self, request):
        match = self.detection_service.detect(request.META.get('HTTP_USER_AGENT'))
        probe = self.detection_service.is_probe_path(request.path)
        if match:
            sentry_sdk.set_tag('agent_family', match.family)
            sentry_sdk.set_tag('agent_kind', match.kind)
        response = self.get_response(request)
        if match or probe:
            self._record(request, response, match, probe)
        return response

    def _record(self, request, response, match, probe):
        try:
            detail = self.request_service.extract_details(request)
            AgentRequest.objects.create(
                family=match.family if match else 'unknown',
                kind=match.kind if match else AgentRequest.Kind.PROBE,
                user_agent=(detail.user_agent or '')[:512],
                path=request.path[:512],
                method=request.method,
                status_code=response.status_code,
                probe=probe,
                authenticated=detail.authenticated,
            )
        except Exception:
            logger.exception('Failed to record agent request')


class AgentTrackingAsgiMiddleware:
    def __init__(self, app):
        self.app = app
        self.detection_service = AgentDetectionService()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        status = {'code': 500}

        async def capture_status(message):
            if message['type'] == 'http.response.start':
                status['code'] = message['status']
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            await sync_to_async(self._record)(scope, status['code'])

    def _record(self, scope, status_code):
        try:
            headers = {key.decode('latin-1'): value.decode('latin-1') for key, value in scope.get('headers', [])}
            user_agent = headers.get('user-agent', '')
            match = self.detection_service.detect(user_agent)
            AgentRequest.objects.create(
                family=match.family if match else 'unknown',
                kind=match.kind if match else AgentRequest.Kind.PROBE,
                user_agent=user_agent[:512],
                path=scope['path'][:512],
                method=scope['method'],
                status_code=status_code,
                probe=self.detection_service.is_probe_path(scope['path']),
                authenticated=False,
            )
        except Exception:
            logger.exception('Failed to record agent request')
