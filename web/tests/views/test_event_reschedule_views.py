from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format

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
        self.assertContains(response, date_format(timezone.localtime(previous_starts_at), 'F j, Y'))
        self.assertContains(response, date_format(timezone.localtime(self.next_week), 'F j, Y'))

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


class RescheduledAllDayEventDisplayTests(TestCase):
    def setUp(self):
        # Arrange
        self.program = Program.objects.create(name="Test Program")
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.next_week = self.now + timedelta(days=7)

        self.event = Event.objects.create(
            program=self.program,
            name="Weekend Tour",
            description="A multi day tour.",
            starts_at=self.tomorrow,
            ends_at=self.tomorrow + timedelta(days=2),
            registration_closes_at=self.now,
            all_day=True,
            state=Event.STATE_LIVE,
        )

        self.detail_url = reverse('event_detail', kwargs={'event_id': self.event.id})

    def local_time(self, moment, hour):
        return timezone.localtime(moment).replace(hour=hour, minute=0, second=0, microsecond=0)

    def test_notice_shows_previous_and_new_date_ranges(self):
        # Arrange
        previous_starts_at = self.event.starts_at
        previous_ends_at = self.event.ends_at
        EventService().reschedule_event(
            self.event,
            starts_at=self.next_week,
            ends_at=self.next_week + timedelta(days=2),
            registration_closes_at=self.next_week - timedelta(hours=1),
            reason='Campground was flooded',
        )

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        for moment in (previous_starts_at, previous_ends_at, self.next_week, self.next_week + timedelta(days=2)):
            self.assertContains(response, date_format(timezone.localtime(moment), 'l, F j, Y'))

    def test_notice_shows_single_date_for_single_day_all_day_event(self):
        # Arrange
        new_starts_at = self.local_time(self.next_week, hour=9)
        new_ends_at = self.local_time(self.next_week, hour=17)
        EventService().reschedule_event(
            self.event,
            starts_at=new_starts_at,
            ends_at=new_ends_at,
            registration_closes_at=new_starts_at - timedelta(hours=1),
            reason='Campground was flooded',
        )

        # Act
        response = self.client.get(self.detail_url)

        # Assert
        new_date_text = date_format(timezone.localtime(new_starts_at), 'l, F j, Y')
        self.assertContains(response, 'Now:</span>')
        self.assertContains(response, new_date_text)
        self.assertNotContains(response, f'{new_date_text} – {new_date_text}')
