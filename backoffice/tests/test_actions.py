from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
from backoffice.models import Program, Event, Registration


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
        self.assertEqual(audit_event.actor, self.admin_user)
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
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.action, 'duplicated')
        self.assertEqual(audit_event.target, duplicated)


class ArchiveEventActionTestCase(TestCase):
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

        self.event = Event.objects.create(
            program=self.program,
            name="Archivable Event",
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )
        self.changelist_url = reverse('admin:backoffice_event_changelist')

    def _add_confirmed_registration(self, event):
        User = get_user_model()
        user = User.objects.create_user(
            username=f'registrant_{event.pk}',
            email=f'registrant_{event.pk}@example.com',
        )
        registration = Registration.objects.create(
            event=event,
            user=user,
            name='Test User',
            first_name='Test',
            last_name='User',
            email=user.email,
            state=Registration.STATE_SUBMITTED,
        )
        registration.confirm()
        registration.save()
        return registration

    def test_archive_action_shows_confirmation_page(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Archive selected events')
        self.assertContains(response, 'archival_reason')
        self.assertContains(response, self.event.name)

    def test_archive_confirmation_page_warns_about_public_visibility(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
        })

        self.assertContains(response, 'no longer be visible on any public page')
        self.assertContains(response, 'cannot be undone')

    def test_archive_action_archives_event(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Created by mistake',
        })

        self.assertRedirects(response, self.changelist_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.STATE_ARCHIVED)
        self.assertEqual(self.event.archival_reason, 'Created by mistake')
        self.assertIsNotNone(self.event.archived_at)

    def test_archive_action_rejects_blank_reason(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An archival reason is required.')
        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.STATE_LIVE)

    def test_archive_action_rejects_whitespace_only_reason(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': '   \n\t  ',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An archival reason is required.')
        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.STATE_LIVE)

    def test_archive_action_strips_surrounding_whitespace_from_reason(self):
        self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': '  Created by mistake  ',
        })

        self.event.refresh_from_db()
        self.assertEqual(self.event.archival_reason, 'Created by mistake')

    def test_archive_action_redisplays_selection_after_blank_reason(self):
        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': '',
        })

        self.assertContains(response, 'Archive selected events')
        self.assertContains(response, self.event.name)
        self.assertContains(response, f'value="{self.event.pk}"')

    def test_archive_action_reports_already_archived_event_distinctly(self):
        self.event.archival_reason = 'Created by mistake'
        self.event.archive()
        self.event.save()

        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Second attempt',
        }, follow=True)

        self.assertContains(response, 'Already archived')
        self.assertNotContains(response, 'must be cancelled before')
        self.event.refresh_from_db()
        self.assertEqual(self.event.archival_reason, 'Created by mistake')

    def test_archive_action_skips_event_with_confirmed_registrations(self):
        self._add_confirmed_registration(self.event)

        response = self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Created by mistake',
        }, follow=True)

        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.STATE_LIVE)
        self.assertContains(response, 'Could not archive')

    def test_archive_action_archives_cancelled_event_with_registrations(self):
        self._add_confirmed_registration(self.event)
        self.event.cancel()
        self.event.save()

        self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Season is over',
        })

        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.STATE_ARCHIVED)

    def test_archive_action_sends_no_email(self):
        self._add_confirmed_registration(self.event)
        self.event.cancel()
        self.event.save()
        mail.outbox = []

        self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Season is over',
        })

        self.assertEqual(len(mail.outbox), 0)

    def test_archive_action_creates_audit_event(self):
        self.client.post(self.changelist_url, {
            'action': 'archive_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'archival_reason': 'Created by mistake',
        })

        audit_event = AuditEvent.objects.get(action='archived')
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.target, Event.objects.get(pk=self.event.pk))

    def test_archived_event_can_be_duplicated(self):
        self.event.archive()
        self.event.save()
        new_date = (self.tomorrow + timedelta(days=7)).strftime('%Y-%m-%d')

        self.client.post(self.changelist_url, {
            'action': 'duplicate_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-event_id': self.event.pk,
            'form-0-new_name': 'Revived Event',
            'form-0-new_date': new_date,
        })

        duplicated = Event.objects.get(name='Revived Event')
        self.assertEqual(duplicated.state, Event.STATE_DRAFT)
        self.assertIsNone(duplicated.archived_at)
        self.assertEqual(duplicated.archival_reason, '')
