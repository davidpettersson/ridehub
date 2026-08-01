from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Program
from backoffice.services.event_service import EventService


class RescheduledEventDisplayTests(TestCase):
    def setUp(self):
        # Arrange
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.next_week = self.now + timedelta(days=7)

        self.event = Event.objects.create(
            program=self.program,
            name="Sunday Ride",
            description="A nice ride.",
            starts_at=self.tomorrow,
            ends_at=self.tomorrow + timedelta(hours=2),
            registration_closes_at=self.now,
            state=Event.STATE_LIVE,
        )

        self.detail_url = reverse('event_detail', kwargs={'event_id': self.event.id})
        self.upcoming_url = reverse('upcoming')

    def reschedule(self):
        EventService().reschedule_event(
            self.event,
            starts_at=self.next_week,
            ends_at=self.next_week + timedelta(hours=2),
            registration_closes_at=self.next_week - timedelta(hours=1),
            reason='Thunderstorms in the forecast',
        )

    def test_detail_page_has_no_notice_when_not_rescheduled(self):
        # Act
        response = self.client.get(self.detail_url)

        # Assert
        self.assertNotContains(response, 'Event Rescheduled')
        self.assertNotContains(response, '(rescheduled)')

    def test_detail_page_shows_reschedule_notice(self):
        # Arrange
        self.reschedule()

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        self.assertContains(response, 'Event Rescheduled')
        self.assertContains(response, 'Thunderstorms in the forecast')

    def test_detail_page_notice_shows_previous_and_new_times(self):
        # Arrange
        previous_starts_at = self.event.starts_at
        self.reschedule()

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        self.assertContains(response, timezone.localtime(previous_starts_at).strftime('%B %-d, %Y'))
        self.assertContains(response, timezone.localtime(self.next_week).strftime('%B %-d, %Y'))

    def test_detail_page_title_has_rescheduled_suffix(self):
        # Arrange
        self.reschedule()

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        self.assertContains(response, '(rescheduled)')

    def test_upcoming_list_has_rescheduled_suffix(self):
        # Arrange
        self.reschedule()

        # Act
        response = self.client.get(self.upcoming_url)

        # Assert
        self.assertContains(response, '(rescheduled)')

    def test_upcoming_list_has_no_suffix_when_not_rescheduled(self):
        # Act
        response = self.client.get(self.upcoming_url)

        # Assert
        self.assertNotContains(response, '(rescheduled)')

    def test_cancelled_suffix_wins_over_rescheduled(self):
        # Arrange
        self.reschedule()
        self.event.cancellation_reason = 'Snow'
        self.event.cancel()
        self.event.save()

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        self.assertContains(response, '(cancelled)')
        self.assertNotContains(response, '(rescheduled)')
        self.assertContains(response, 'Event Rescheduled')
