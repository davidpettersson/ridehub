from dataclasses import dataclass

from django.contrib.auth.models import User
from returns.maybe import Maybe, Some, Nothing

from backoffice.utils import ensure, lower_email


@dataclass
class UserDetail:
    first_name: str
    last_name: str
    email: str
    phone: str


class UserService(object):
    def find_by_email(self, email: str) -> Maybe[User]:
        lowercase_email = lower_email(email)
        users = User.objects.filter(email=lowercase_email)
        ensure(users.count() <= 1, "zero or one users for a given email")

        if users.count() == 1:
            user = users.first()
            return Some(user)
        else:
            return Nothing

    def find_by_email_or_create(self, user_detail: UserDetail) -> User:
        lowercase_email = lower_email(user_detail.email)

        match self.find_by_email(lowercase_email):
            case Some(user):
                if not user.is_staff:
                    user.set_unusable_password()

                user.first_name = user_detail.first_name
                user.last_name = user_detail.last_name
                user.save()

                user.profile.phone = user_detail.phone
                user.profile.save()

                return user
            case _:
                user = User.objects.create_user(
                    username=lowercase_email,
                    email=lowercase_email,
                    first_name=user_detail.first_name,
                    last_name=user_detail.last_name,
                )

                user.set_unusable_password()
                user.save()

                user.profile.phone = user_detail.phone
                user.profile.save()

                return user
