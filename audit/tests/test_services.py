from django.contrib.auth.models import User
from django.test import TestCase

from audit.models import AuditEvent
from audit.services import AuditService


class AuditServiceTestCase(TestCase):
    def test_log_creates_event_with_target(self):
        # Arrange
        actor = User.objects.create(username='staff')
        target = User.objects.create(username='affected')
        service = AuditService()

        # Act
        event = service.log(actor, 'updated', target=target)

        # Assert
        self.assertEqual(event.actor, actor)
        self.assertEqual(event.action, 'updated')
        self.assertEqual(event.target, target)
        self.assertEqual(event.target_repr, str(target))
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_log_without_target(self):
        # Arrange
        actor = User.objects.create(username='staff')
        service = AuditService()

        # Act
        event = service.log(actor, 'created')

        # Assert
        self.assertIsNone(event.target)
        self.assertEqual(event.target_repr, '')
