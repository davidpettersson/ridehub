import logging

import sentry_sdk

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
