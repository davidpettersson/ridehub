from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from audit.context import actor
from audit.models import AuditEvent
from backoffice.admin import ProgramAdmin
from backoffice.models import Program


class AuditSignalsTestCase(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='password',
        )

    def test_saving_model_with_actor_context_creates_audit_event(self):
        # Arrange
        program = Program(name='Test Program')

        # Act
        with actor(self.staff_user):
            program.save()

        # Assert
        events = AuditEvent.objects.filter(subject=self.staff_user)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().action, 'created')

    def test_updating_model_with_actor_context_logs_updated(self):
        # Arrange
        program = Program.objects.create(name='Test Program')

        # Act
        with actor(self.staff_user):
            program.name = 'Renamed Program'
            program.save()

        # Assert
        events = AuditEvent.objects.filter(subject=self.staff_user, action='updated')
        self.assertEqual(events.count(), 1)

    def test_deleting_model_with_actor_context_logs_deleted(self):
        # Arrange
        program = Program.objects.create(name='Test Program')

        # Act
        with actor(self.staff_user):
            program.delete()

        # Assert
        events = AuditEvent.objects.filter(subject=self.staff_user, action='deleted')
        self.assertEqual(events.count(), 1)

    def test_saving_model_without_actor_context_creates_no_audit_event(self):
        # Arrange
        program = Program(name='Test Program')

        # Act
        program.save()

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_admin_bulk_delete_logs_deleted_per_object(self):
        # Arrange
        Program.objects.create(name='Program A')
        Program.objects.create(name='Program B')
        model_admin = ProgramAdmin(Program, AdminSite())
        request = RequestFactory().post('/')
        request.user = self.staff_user

        # Act
        model_admin.delete_queryset(request, Program.objects.all())

        # Assert
        events = AuditEvent.objects.filter(subject=self.staff_user, action='deleted')
        self.assertEqual(events.count(), 2)
