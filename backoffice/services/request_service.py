from dataclasses import dataclass

from backoffice.utils import lower_email


@dataclass
class RequestDetail:
    ip_address: str | None
    user_agent: str | None
    authenticated: bool
    user_id: int | None = None
    user_email: str | None = None


class RequestService:
    def extract_details(self, request) -> RequestDetail:
        user_id = None
        user_email = None
        if request.user.is_authenticated:
            user_id = request.user.id
            user_email = lower_email(request.user.email)

        return RequestDetail(
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            authenticated=request.user.is_authenticated,
            user_id=user_id,
            user_email=user_email,
        )

    def _get_client_ip(self, request) -> str | None:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
