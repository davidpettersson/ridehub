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
        year = timezone.now().year
        normalized_number = number.strip()

        membership_number, created = UserMembershipNumber.objects.get_or_create(
            user=user,
            year=year,
            defaults={'number': normalized_number},
        )

        if not created and membership_number.number != normalized_number:
            membership_number.number = normalized_number
            membership_number.save(update_fields=['number', 'updated_at'])

        return membership_number
