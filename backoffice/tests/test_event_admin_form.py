from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.forms import EventAdminForm
from backoffice.models import Event, Program, Registration


class TestEventAdminForm(EventAdminForm):
    class Meta(EventAdminForm.Meta):
        widgets = {}


class EventAdminFormTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

    def create_event(self, state=Event.STATE_LIVE):
        event = Event.objects.create(
            program=self.program,
            name='Test Event',
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
            description='Test description',
        )
        if state == Event.STATE_DRAFT:
            event.draft()
            event.save()
        elif state == Event.STATE_ANNOUNCED:
            event.announce()
            event.save()
        elif state == Event.STATE_CANCELLED:
            event.cancel()
            event.save()
        elif state == Event.STATE_ARCHIVED:
            event.archive()
            event.save()
        return event

    def _get_form_data(self, event, **overrides):
        fmt = '%Y-%m-%d %H:%M:%S'
        data = {
            'program': event.program_id,
            'name': event.name,
            'starts_at': event.starts_at.strftime(fmt),
            'registration_closes_at': event.registration_closes_at.strftime(fmt),
            'description': event.description,
            'state': event.state,
            'virtual': event.virtual,
            'ride_leaders_wanted': event.ride_leaders_wanted,
            'requires_emergency_contact': event.requires_emergency_contact,
            'requires_membership': event.requires_membership,
        }
        data.update(overrides)
        return data

    def _add_confirmed_registration(self, event):
        user = User.objects.create_user(
            username=f'testuser_{event.pk}',
            email=f'test_{event.pk}@example.com',
        )
        reg = Registration.objects.create(
            event=event,
            user=user,
            name='Test User',
            first_name='Test',
            last_name='User',
            email=user.email,
            state=Registration.STATE_SUBMITTED,
        )
        reg.confirm()
        reg.save()
        return reg

    def test_state_change_via_form_triggers_transition(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        data = self._get_form_data(event, state=Event.STATE_ANNOUNCED)

        form = TestEventAdminForm(data=data, instance=event)
        self.assertTrue(form.is_valid(), form.errors)
        saved_event = form.save()

        self.assertEqual(saved_event.state, Event.STATE_ANNOUNCED)

    def test_invalid_transition_raises_validation_error(self):
        event = self.create_event(state=Event.STATE_CANCELLED)
        data = self._get_form_data(event, state=Event.STATE_DRAFT)

        form = TestEventAdminForm(data=data, instance=event)
        self.assertFalse(form.is_valid())

    def test_guard_blocks_transition_with_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self._add_confirmed_registration(event)
        data = self._get_form_data(event, state=Event.STATE_DRAFT)

        form = TestEventAdminForm(data=data, instance=event)
        self.assertFalse(form.is_valid())

    def test_guard_allows_transition_without_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)
        data = self._get_form_data(event, state=Event.STATE_DRAFT)

        form = TestEventAdminForm(data=data, instance=event)
        self.assertTrue(form.is_valid(), form.errors)
        saved_event = form.save()

        self.assertEqual(saved_event.state, Event.STATE_DRAFT)

    def test_cancelled_not_in_state_choices(self):
        event = self.create_event(state=Event.STATE_LIVE)
        form = TestEventAdminForm(instance=event)
        state_values = [value for value, _ in form.fields['state'].choices]
        self.assertNotIn(Event.STATE_CANCELLED, state_values)

    def test_archived_not_in_state_choices(self):
        event = self.create_event(state=Event.STATE_LIVE)
        form = TestEventAdminForm(instance=event)
        state_values = [value for value, _ in form.fields['state'].choices]
        self.assertNotIn(Event.STATE_ARCHIVED, state_values)

    def test_no_state_change_saves_normally(self):
        event = self.create_event(state=Event.STATE_LIVE)
        data = self._get_form_data(event, name='Updated Name')

        form = TestEventAdminForm(data=data, instance=event)
        self.assertTrue(form.is_valid(), form.errors)
        saved_event = form.save()

        self.assertEqual(saved_event.name, 'Updated Name')
        self.assertEqual(saved_event.state, Event.STATE_LIVE)
