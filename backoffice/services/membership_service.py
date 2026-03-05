from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import UserMembershipNumber


class MembershipService:
    def get_current_membership_number(self, user: User) -> UserMembershipNumber | None:
        return UserMembershipNumber.objects.filter(
            user=user,
            year=timezone.now().year,
        ).first()

    def has_current_membership_number(self, user: User) -> bool:
        return self.get_current_membership_number(user) is not None

    def save_membership_number(self, user: User, number: str) -> UserMembershipNumber:
        return UserMembershipNumber.objects.create(
            user=user,
            number=number.strip(),
            year=timezone.now().year,
        )
