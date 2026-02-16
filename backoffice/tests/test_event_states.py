from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from backoffice.models import Program, Event


class EventStatesTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")

        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

    def create_event(self, state=Event.STATE_OPEN, **kwargs):
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

    def test_new_event_defaults_to_open(self):
        event = Event.objects.create(
            program=self.program,
            name='Test Event',
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )

        self.assertEqual(event.state, Event.STATE_OPEN)

    def test_open_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

        event.open()
        event.save()

        self.assertEqual(event.state, Event.STATE_OPEN)
        self.assertTrue(event.visible)

    def test_open_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        event.open()
        event.save()

        self.assertEqual(event.state, Event.STATE_OPEN)
        self.assertTrue(event.visible)

    def test_announce_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        event.announce()
        event.save()

        self.assertEqual(event.state, Event.STATE_ANNOUNCED)
        self.assertTrue(event.visible)

    def test_announce_from_open(self):
        event = self.create_event(state=Event.STATE_OPEN)
        self.assertEqual(event.state, Event.STATE_OPEN)

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

    def test_draft_from_open(self):
        event = self.create_event(state=Event.STATE_OPEN)
        self.assertEqual(event.state, Event.STATE_OPEN)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

    def test_cancel_from_open(self):
        event = self.create_event(state=Event.STATE_OPEN)
        self.assertEqual(event.state, Event.STATE_OPEN)
        self.assertFalse(event.cancelled)
        self.assertIsNone(event.cancelled_at)

        event.cancel()
        event.save()

        self.assertEqual(event.state, Event.STATE_CANCELLED)
        self.assertTrue(event.cancelled)
        self.assertIsNotNone(event.cancelled_at)

    def test_archive_from_open(self):
        event = self.create_event(state=Event.STATE_OPEN)
        self.assertEqual(event.state, Event.STATE_OPEN)
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

    def test_cannot_open_from_cancelled(self):
        event = self.create_event(state=Event.STATE_CANCELLED)
        self.assertEqual(event.state, Event.STATE_CANCELLED)

        with self.assertRaises(TransitionNotAllowed):
            event.open()

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

    def test_cannot_open_from_archived(self):
        event = self.create_event(state=Event.STATE_ARCHIVED)
        self.assertEqual(event.state, Event.STATE_ARCHIVED)

        with self.assertRaises(TransitionNotAllowed):
            event.open()

    def test_cannot_cancel_from_announced(self):
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.assertEqual(event.state, Event.STATE_ANNOUNCED)

        with self.assertRaises(TransitionNotAllowed):
            event.cancel()


class EventAdminFieldsetsTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

    def create_event(self, state=Event.STATE_OPEN):
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

    def test_cancellation_fieldset_hidden_for_open_event(self):
        from backoffice.admin import EventAdmin

        event = self.create_event(state=Event.STATE_OPEN)
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
