from datetime import timedelta

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
from backoffice.actions import archive_event
from backoffice.models import Program, Event


class EventAdminActionsTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )
        self.client.login(username='admin', password='adminpass')

    def create_event(self, name='Test Event'):
        return Event.objects.create(
            program=self.program,
            name=name,
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )

    def test_cancel_action_shows_confirmation_page(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cancel selected events')
        self.assertContains(response, 'cancellation_reason')
        self.assertContains(response, event.name)

    def test_cancel_action_cancels_event(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': 'Bad weather',
        })

        self.assertRedirects(response, changelist_url)
        event.refresh_from_db()
        self.assertEqual(event.state, Event.STATE_CANCELLED)
        self.assertEqual(event.cancellation_reason, 'Bad weather')

    def test_duplicate_action_shows_form(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'duplicate_event',
            '_selected_action': [event.pk],
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Duplicate selected events')
        self.assertContains(response, event.name)
        self.assertContains(response, 'new_name')
        self.assertContains(response, 'new_date')

    def test_duplicate_action_creates_new_event(self):
        event = self.create_event(name='Original Event')
        changelist_url = reverse('admin:backoffice_event_changelist')
        new_date = (self.tomorrow + timedelta(days=7)).strftime('%Y-%m-%d')

        response = self.client.post(changelist_url, {
            'action': 'duplicate_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-event_id': event.pk,
            'form-0-new_name': 'Duplicated Event',
            'form-0-new_date': new_date,
        })

        self.assertRedirects(response, changelist_url)
        self.assertEqual(Event.objects.count(), 2)
        duplicated = Event.objects.get(name='Duplicated Event')
        self.assertEqual(duplicated.program, event.program)

    def test_cancel_action_creates_audit_event(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': 'Bad weather',
        })

        audit_event = AuditEvent.objects.get()
        self.assertEqual(audit_event.subject, self.admin_user)
        self.assertEqual(audit_event.action, 'cancelled')
        self.assertEqual(audit_event.target, Event.objects.get(pk=event.pk))

    def test_duplicate_action_creates_audit_event(self):
        event = self.create_event(name='Original Event')
        changelist_url = reverse('admin:backoffice_event_changelist')
        new_date = (self.tomorrow + timedelta(days=7)).strftime('%Y-%m-%d')

        self.client.post(changelist_url, {
            'action': 'duplicate_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-event_id': event.pk,
            'form-0-new_name': 'Duplicated Event',
            'form-0-new_date': new_date,
        })

        duplicated = Event.objects.get(name='Duplicated Event')
        audit_event = AuditEvent.objects.get()
        self.assertEqual(audit_event.subject, self.admin_user)
        self.assertEqual(audit_event.action, 'duplicated')
        self.assertEqual(audit_event.target, duplicated)


class ArchiveEventActionTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.factory = RequestFactory()

        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )
        self.event = Event.objects.create(
            program=self.program,
            name="Archivable Event",
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )
        self.model_admin = django_admin.ModelAdmin(Event, django_admin.site)

    def _request(self):
        request = self.factory.post('/admin/backoffice/event/')
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_archive_event_creates_audit_event(self):
        request = self._request()

        archive_event(self.model_admin, request, Event.objects.filter(pk=self.event.pk))

        audit_event = AuditEvent.objects.get()
        self.assertEqual(audit_event.subject, self.admin_user)
        self.assertEqual(audit_event.action, 'archived')
        self.assertEqual(audit_event.target, Event.objects.get(pk=self.event.pk))
