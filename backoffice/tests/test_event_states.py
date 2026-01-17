from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Program, Event


class EventStatesTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")

        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)

    def create_event(self, state=Event.STATE_PUBLISHED, **kwargs):
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
        elif state == Event.STATE_PREVIEW:
            event.preview()
            event.save()
        elif state == Event.STATE_CANCELLED:
            event.cancel()
            event.save()
        elif state == Event.STATE_ARCHIVED:
            event.archive()
            event.save()

        return event

    def test_new_event_defaults_to_published(self):
        event = Event.objects.create(
            program=self.program,
            name='Test Event',
            starts_at=self.tomorrow,
            registration_closes_at=self.now,
        )

        self.assertEqual(event.state, Event.STATE_PUBLISHED)

    def test_publish_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

        event.publish()
        event.save()

        self.assertEqual(event.state, Event.STATE_PUBLISHED)
        self.assertTrue(event.visible)

    def test_publish_from_preview(self):
        event = self.create_event(state=Event.STATE_PREVIEW)
        self.assertEqual(event.state, Event.STATE_PREVIEW)

        event.publish()
        event.save()

        self.assertEqual(event.state, Event.STATE_PUBLISHED)
        self.assertTrue(event.visible)

    def test_preview_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        event.preview()
        event.save()

        self.assertEqual(event.state, Event.STATE_PREVIEW)

    def test_preview_from_published(self):
        event = self.create_event(state=Event.STATE_PUBLISHED)
        self.assertEqual(event.state, Event.STATE_PUBLISHED)

        event.preview()
        event.save()

        self.assertEqual(event.state, Event.STATE_PREVIEW)

    def test_draft_from_preview(self):
        event = self.create_event(state=Event.STATE_PREVIEW)
        self.assertEqual(event.state, Event.STATE_PREVIEW)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

    def test_draft_from_published(self):
        event = self.create_event(state=Event.STATE_PUBLISHED)
        self.assertEqual(event.state, Event.STATE_PUBLISHED)

        event.draft()
        event.save()

        self.assertEqual(event.state, Event.STATE_DRAFT)
        self.assertFalse(event.visible)

    def test_cancel_from_published(self):
        event = self.create_event(state=Event.STATE_PUBLISHED)
        self.assertEqual(event.state, Event.STATE_PUBLISHED)
        self.assertFalse(event.cancelled)
        self.assertIsNone(event.cancelled_at)

        event.cancel()
        event.save()

        self.assertEqual(event.state, Event.STATE_CANCELLED)
        self.assertTrue(event.cancelled)
        self.assertIsNotNone(event.cancelled_at)

    def test_archive_from_published(self):
        event = self.create_event(state=Event.STATE_PUBLISHED)
        self.assertEqual(event.state, Event.STATE_PUBLISHED)
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

    def test_cannot_publish_from_cancelled(self):
        event = self.create_event(state=Event.STATE_CANCELLED)
        self.assertEqual(event.state, Event.STATE_CANCELLED)

        with self.assertRaises(Exception):
            event.publish()

    def test_cannot_cancel_from_draft(self):
        event = self.create_event(state=Event.STATE_DRAFT)
        self.assertEqual(event.state, Event.STATE_DRAFT)

        with self.assertRaises(Exception):
            event.cancel()

    def test_cannot_cancel_from_archived(self):
        event = self.create_event(state=Event.STATE_ARCHIVED)
        self.assertEqual(event.state, Event.STATE_ARCHIVED)

        with self.assertRaises(Exception):
            event.cancel()
