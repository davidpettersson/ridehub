from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from backoffice.models import Program, Event, Registration


class EventStatesTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")

        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

    def create_event(self, state=Event.STATE_LIVE, **kwargs):
        defaults = {
            'program': self.program,
            'name': 'Test Event',
            'starts_at': self.tomorrow,
            'registration_closes_at': self.now,
        }
        defaults.update(kwargs)
        event = Event.objects.create(**defaults)

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

    def test_new_event_defaults_to_live(self):
        event = Event.objects.create(
            program=self.program,
            name='Test Event',
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )

        self.assertEqual(event.state, Event.STATE_LIVE)

    def test_live_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

        event.live()
        event.save()

        self.assertEqual(event.state, Event.STATE_LIVE)
        self.assertTrue(event.visible)

    def test_live_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        event.live()
        event.save()

        self.assertEqual(event.state, Event.STATE_LIVE)
        self.assertTrue(event.visible)

    def test_announce_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        event.announce()
        event.save()

        self.assertEqual(event.state, Event.STATE_ANNOUNCED)
        self.assertTrue(event.visible)

    def test_announce_from_live(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self.assertEqual(event.state, Event.STATE_LIVE)

        event.announce()
        event.save()

        self.assertEqual(event.state, Event.STATE_ANNOUNCED)
        self.assertTrue(event.visible)

    def test_draft_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

    def test_draft_from_live(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self.assertEqual(event.state, Event.STATE_LIVE)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

    def test_cancel_from_live(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self.assertEqual(event.state, Event.STATE_LIVE)
        self.assertFalse(event.cancelled)
        self.assertIsNone(event.cancelled_at)

        event.cancel()
        event.save()

        self.assertEqual(event.state, Event.STATE_CANCELLED)
        self.assertTrue(event.cancelled)
        self.assertIsNotNone(event.cancelled_at)

    def test_archive_from_live(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self.assertEqual(event.state, Event.STATE_LIVE)
        self.assertFalse(event.archived)
        self.assertIsNone(event.archived_at)

        event.archive()
        event.save()

        self.assertEqual(event.state, Event.STATE_ARCHIVED)
        self.assertTrue(event.archived)
        self.assertIsNotNone(event.archived_at)

    def test_archive_from_cancelled(self):
        event = self.create_event(state=Event.STATE_CANCELLED)
        self.assertEqual(event.state, Event.STATE_CANCELLED)

        event.archive()
        event.save()

        self.assertEqual(event.state, Event.STATE_ARCHIVED)
        self.assertTrue(event.archived)
        self.assertIsNotNone(event.archived_at)

    def test_cannot_live_from_cancelled(self):
        event = self.create_event(state=Event.STATE_CANCELLED)
        self.assertEqual(event.state, Event.STATE_CANCELLED)

        with self.assertRaises(TransitionNotAllowed):
            event.live()

    def test_cannot_cancel_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        with self.assertRaises(TransitionNotAllowed):
            event.cancel()

    def test_cannot_cancel_from_archived(self):
        event = self.create_event(state=Event.STATE_ARCHIVED)
        self.assertEqual(event.state, Event.STATE_ARCHIVED)

        with self.assertRaises(TransitionNotAllowed):
            event.cancel()

    def test_cannot_archive_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        with self.assertRaises(TransitionNotAllowed):
            event.archive()

    def test_cannot_archive_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        with self.assertRaises(TransitionNotAllowed):
            event.archive()

    def test_cannot_live_from_archived(self):
        event = self.create_event(state=Event.STATE_ARCHIVED)
        self.assertEqual(event.state, Event.STATE_ARCHIVED)

        with self.assertRaises(TransitionNotAllowed):
            event.live()

    def test_cannot_cancel_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        with self.assertRaises(TransitionNotAllowed):
            event.cancel()

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

    def test_cannot_draft_from_live_with_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self._add_confirmed_registration(event)

        with self.assertRaises(TransitionNotAllowed):
            event.draft()

    def test_cannot_announce_from_live_with_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)
        self._add_confirmed_registration(event)

        with self.assertRaises(TransitionNotAllowed):
            event.announce()

    def test_can_draft_from_live_without_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)

    def test_can_announce_from_live_without_registrations(self):
        event = self.create_event(state=Event.STATE_LIVE)

        event.announce()
        event.save()

        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

    def test_visible_property_by_state(self):
        for state, expected in [
            (Event.STATE_DRAFT, False),
            (Event.STATE_ANNOUNCED, True),
            (Event.STATE_LIVE, True),
            (Event.STATE_CANCELLED, True),
            (Event.STATE_ARCHIVED, False),
        ]:
            event = self.create_event(state=state)
            self.assertEqual(event.visible, expected, f"visible should be {expected} for state {state}")

    def test_cancelled_property_by_state(self):
        for state, expected in [
            (Event.STATE_DRAFT, False),
            (Event.STATE_ANNOUNCED, False),
            (Event.STATE_LIVE, False),
            (Event.STATE_CANCELLED, True),
            (Event.STATE_ARCHIVED, False),
        ]:
            event = self.create_event(state=state)
            self.assertEqual(event.cancelled, expected, f"cancelled should be {expected} for state {state}")

    def test_archived_property_by_state(self):
        for state, expected in [
            (Event.STATE_DRAFT, False),
            (Event.STATE_ANNOUNCED, False),
            (Event.STATE_LIVE, False),
            (Event.STATE_CANCELLED, False),
            (Event.STATE_ARCHIVED, True),
        ]:
            event = self.create_event(state=state)
            self.assertEqual(event.archived, expected, f"archived should be {expected} for state {state}")

    def test_registration_open_only_in_live_state(self):
        future_close = self.now + timedelta(hours=12)
        for state in [Event.STATE_DRAFT, Event.STATE_ANNOUNCED, Event.STATE_CANCELLED, Event.STATE_ARCHIVED]:
            event = self.create_event(state=state, registration_closes_at=future_close)
            self.assertFalse(event.registration_open, f"registration_open should be False for state {state}")

        event = self.create_event(state=Event.STATE_LIVE, registration_closes_at=future_close)
        self.assertTrue(event.registration_open)


class EventAdminFieldsetsTestCase(TestCase):
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
        )
        if state == Event.STATE_CANCELLED:
            event.cancel()
            event.save()
        return event

    def get_fieldset_names(self, fieldsets):
        return [name for name, _ in fieldsets]

    def test_cancellation_fieldset_hidden_for_live_event(self):
        from backoffice.admin import EventAdmin

        event = self.create_event(state=Event.STATE_LIVE)
        admin = EventAdmin(Event, None)

        fieldsets = admin.get_fieldsets(None, obj=event)
        fieldset_names = self.get_fieldset_names(fieldsets)

        self.assertNotIn('Cancellation information', fieldset_names)

    def test_cancellation_fieldset_hidden_for_new_event(self):
        from backoffice.admin import EventAdmin

        admin = EventAdmin(Event, None)

        fieldsets = admin.get_fieldsets(None, obj=None)
        fieldset_names = self.get_fieldset_names(fieldsets)

        self.assertNotIn('Cancellation information', fieldset_names)

    def test_cancellation_fieldset_shown_for_cancelled_event(self):
        from backoffice.admin import EventAdmin

        event = self.create_event(state=Event.STATE_CANCELLED)
        admin = EventAdmin(Event, None)

        fieldsets = admin.get_fieldsets(None, obj=event)
        fieldset_names = self.get_fieldset_names(fieldsets)

        self.assertIn('Cancellation information', fieldset_names)
