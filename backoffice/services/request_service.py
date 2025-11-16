from dataclasses import dataclass


@dataclass
class RequestDetail:
    ip_address: str | None
    user_agent: str | None
    is_authenticated: bool


class RequestService:
    def extract_details(self, request) -> RequestDetail:
        return RequestDetail(
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            is_authenticated=request.user.is_authenticated
        )

    def _get_client_ip(self, request) -> str | None:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
