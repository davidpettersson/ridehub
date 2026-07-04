from django.contrib.auth.models import User
from django.test import TestCase

from audit.context import actor, get_actor


class AuditContextTestCase(TestCase):
    def test_actor_is_set_within_context_and_cleared_after(self):
        # Arrange
        user = User.objects.create(username='staff')
        self.assertIsNone(get_actor())

        # Act / Assert
        with actor(user):
            self.assertEqual(get_actor(), user)
        self.assertIsNone(get_actor())
