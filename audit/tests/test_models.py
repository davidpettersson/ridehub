from django.contrib.auth.models import User
from django.test import TestCase

from audit.models import AuditEvent


class AuditEventTestCase(TestCase):
    def test_target_repr_survives_target_deletion(self):
        # Arrange
        actor = User.objects.create(username='staff')
        target = User.objects.create(username='deleteme')
        event = AuditEvent.objects.create(actor=actor, action='updated', target=target,
                                           target_repr=str(target))

        # Act
        target.delete()
        event.refresh_from_db()

        # Assert
        self.assertEqual(event.target_repr, 'deleteme')
        self.assertIsNone(event.target)

    def test_str_includes_actor_action_and_target(self):
        # Arrange
        actor = User.objects.create(username='staff')

        # Act
        event = AuditEvent.objects.create(actor=actor, action='created', target_repr='thing')

        # Assert
        self.assertEqual(str(event), 'staff created thing')
