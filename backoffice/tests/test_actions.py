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

    def test_cancel_action_rejects_blank_reason(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A cancellation reason is required.')
        event.refresh_from_db()
        self.assertEqual(event.state, Event.STATE_LIVE)

    def test_cancel_action_rejects_whitespace_only_reason(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': '   \n\t  ',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A cancellation reason is required.')
        event.refresh_from_db()
        self.assertEqual(event.state, Event.STATE_LIVE)

    def test_cancel_action_sends_no_email_when_reason_is_blank(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')
        mail.outbox = []

        self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': '',
        })

        self.assertEqual(len(mail.outbox), 0)

    def test_cancel_action_strips_surrounding_whitespace_from_reason(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': '  Bad weather  ',
        })

        event.refresh_from_db()
        self.assertEqual(event.cancellation_reason, 'Bad weather')

    def test_cancel_action_redisplays_selection_after_blank_reason(self):
        event = self.create_event()
        changelist_url = reverse('admin:backoffice_event_changelist')

        response = self.client.post(changelist_url, {
            'action': 'cancel_event',
            '_selected_action': [event.pk],
            'post': 'yes',
            'cancellation_reason': '',
        })

        self.assertContains(response, 'Cancel selected events')
        self.assertContains(response, event.name)
        self.assertContains(response, f'value="{event.pk}"')

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


class EventRescheduleActionTestCase(TestCase):
    def setUp(self):
        # Arrange
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.next_week = self.now + timedelta(days=7)
        self.changelist_url = reverse('admin:backoffice_event_changelist')

        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )
        self.client.login(username='admin', password='adminpass')

        self.event = self.create_event()

    def create_event(self, name='Test Event'):
        return Event.objects.create(
            program=self.program,
            name=name,
            starts_at=self.tomorrow,
            ends_at=self.tomorrow + timedelta(hours=2),
            registration_closes_at=self.now,
            state=Event.STATE_LIVE,
        )

    def create_confirmed_registration(self, email='rider@example.com'):
        return Registration.objects.create(
            event=self.event,
            name='Rider',
            email=email,
            state=Registration.STATE_CONFIRMED,
        )

    def local_input(self, moment):
        return timezone.localtime(moment).strftime('%Y-%m-%dT%H:%M')

    def post_reschedule(self, **overrides):
        data = {
            'action': 'reschedule_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'starts_at': self.local_input(self.next_week),
            'ends_at': self.local_input(self.next_week + timedelta(hours=2)),
            'registration_closes_at': self.local_input(self.next_week - timedelta(hours=1)),
            'reschedule_reason': 'Thunderstorms',
            'notify_registrants': 'on',
        }
        data.update(overrides)
        return self.client.post(self.changelist_url, data)

    def test_action_shows_reschedule_page(self):
        # Act
        response = self.client.post(self.changelist_url, {
            'action': 'reschedule_event',
            '_selected_action': [self.event.pk],
        })

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reschedule event')
        self.assertContains(response, 'reschedule_reason')
        self.assertContains(response, self.event.name)

    def test_action_reschedules_event(self):
        # Act
        response = self.post_reschedule()

        # Assert
        self.assertRedirects(response, self.changelist_url)
        event = Event.objects.get(pk=self.event.pk)
        self.assertEqual(event.previous_starts_at, self.tomorrow)
        self.assertEqual(event.reschedule_reason, 'Thunderstorms')
        self.assertTrue(event.rescheduled)

    def test_action_notifies_confirmed_registrants(self):
        # Arrange
        self.create_confirmed_registration()

        # Act
        self.post_reschedule()

        # Assert
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('RIDE RESCHEDULED', mail.outbox[0].subject)

    def test_action_skips_notification_when_unchecked(self):
        # Arrange
        self.create_confirmed_registration()

        # Act
        response = self.post_reschedule(notify_registrants='')

        # Assert
        self.assertRedirects(response, self.changelist_url)
        self.assertEqual(len(mail.outbox), 0)

    def test_action_creates_audit_event(self):
        # Act
        self.post_reschedule()

        # Assert
        audit_event = AuditEvent.objects.get(action='rescheduled')
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.target, Event.objects.get(pk=self.event.pk))

    def test_action_requires_exactly_one_event(self):
        # Arrange
        other_event = self.create_event(name='Other Event')

        # Act
        response = self.client.post(self.changelist_url, {
            'action': 'reschedule_event',
            '_selected_action': [self.event.pk, other_event.pk],
        })

        # Assert
        self.assertRedirects(response, self.changelist_url)
        self.assertFalse(Event.objects.get(pk=self.event.pk).rescheduled)

    def test_action_rejects_cancelled_event(self):
        # Arrange
        self.event.cancellation_reason = 'Snow'
        self.event.cancel()
        self.event.save()

        # Act
        response = self.client.post(self.changelist_url, {
            'action': 'reschedule_event',
            '_selected_action': [self.event.pk],
        })

        # Assert
        self.assertRedirects(response, self.changelist_url)
        self.assertFalse(Event.objects.get(pk=self.event.pk).rescheduled)

    def test_action_rejects_start_in_the_past(self):
        # Act
        response = self.post_reschedule(starts_at=self.local_input(self.now - timedelta(days=1)))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot start in the past')
        self.assertFalse(Event.objects.get(pk=self.event.pk).rescheduled)

    def test_action_rejects_unchanged_start(self):
        # Act
        response = self.post_reschedule(starts_at=self.local_input(self.tomorrow))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'must differ from the current start time')

    def test_action_rejects_registration_closing_after_start(self):
        # Act
        response = self.post_reschedule(
            registration_closes_at=self.local_input(self.next_week + timedelta(hours=1))
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registration cannot close after the event starts')
        self.assertFalse(Event.objects.get(pk=self.event.pk).rescheduled)

    def test_action_rejects_end_before_start(self):
        # Act
        response = self.post_reschedule(ends_at=self.local_input(self.next_week - timedelta(hours=2)))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'End time cannot be before the start time')

    def test_action_rejects_missing_reason(self):
        # Act
        response = self.post_reschedule(reschedule_reason='   ')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.get(pk=self.event.pk).rescheduled)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_does_not_carry_over_reschedule_status(self):
        # Arrange
        self.post_reschedule()
        new_date = (self.next_week + timedelta(days=7)).strftime('%Y-%m-%d')

        # Act
        self.client.post(self.changelist_url, {
            'action': 'duplicate_event',
            '_selected_action': [self.event.pk],
            'post': 'yes',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-event_id': self.event.pk,
            'form-0-new_name': 'Fresh Event',
            'form-0-new_date': new_date,
        })

        # Assert
        duplicated = Event.objects.get(name='Fresh Event')
        self.assertFalse(duplicated.rescheduled)
        self.assertIsNone(duplicated.previous_starts_at)
        self.assertEqual(duplicated.reschedule_reason, '')
