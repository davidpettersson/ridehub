from dataclasses import dataclass

from django.contrib.auth.models import User
from returns.maybe import Maybe, Some, Nothing

from backoffice.utils import ensure


@dataclass
class UserDetail:
    first_name: str
    last_name: str
    email: str


class UserService(object):
    def find_by_email(self, email: str) -> Maybe[User]:
        users = User.objects.filter(email=email)
        ensure(users.count() <= 1, "zero or one users for a given email")
        if users.count() == 1:
            return Some(users.first())
        else:
            return Nothing

    def find_by_email_or_create(self, user_detail: UserDetail) -> User:
        match self.find_by_email(user_detail.email):
            case Some(user):
                if not user.is_staff:
                    user.first_name = user_detail.first_name
                    user.last_name = user_detail.last_name
                    user.set_unusable_password()
                    user.save()
                return user
            case _:
                user = User.objects.create_user(
                    username=user_detail.email,
                    email=user_detail.email,
                    first_name=user_detail.first_name,
                    last_name=user_detail.last_name,
                )
                user.set_unusable_password()
                user.save()
                return user
