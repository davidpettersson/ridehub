import datetime
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Announcement
from backoffice.services.announcement_service import AnnouncementService


class BaseAnnouncementServiceTest(TestCase):
    def setUp(self):
        # Arrange - Common setup for all test cases
        self.now = timezone.now()
        self.one_hour_ago = self.now - timedelta(hours=1)
        self.one_hour_from_now = self.now + timedelta(hours=1)
        self.two_hours_ago = self.now - timedelta(hours=2)
        self.two_hours_from_now = self.now + timedelta(hours=2)

        # Create test announcements
        self._create_test_announcements()

        # Create service instance
        self.service = AnnouncementService()

    def _create_test_announcements(self):
        # Active announcement (started 1 hour ago, ends in 1 hour)
        Announcement.objects.create(
            title="Currently Active",
            text="This announcement is currently active",
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        # Future announcement (starts in 1 hour, ends in 2 hours)
        Announcement.objects.create(
            title="Future Announcement",
            text="This announcement will be active in the future",
            begin_at=self.one_hour_from_now,
            end_at=self.two_hours_from_now,
        )

        # Past announcement (started 2 hours ago, ended 1 hour ago)
        Announcement.objects.create(
            title="Past Announcement",
            text="This announcement was active in the past",
            begin_at=self.two_hours_ago,
            end_at=self.one_hour_ago,
        )

        # Announcement starting now
        Announcement.objects.create(
            title="Starting Now",
            text="This announcement starts exactly now",
            begin_at=self.now,
            end_at=self.one_hour_from_now,
        )

        # Announcement ending now
        Announcement.objects.create(
            title="Ending Now",
            text="This announcement ends exactly now",
            begin_at=self.one_hour_ago,
            end_at=self.now,
        )


class FetchActiveAnnouncementsTests(BaseAnnouncementServiceTest):
    def test_returns_currently_active_announcements(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        self.assertEqual(3, result.count(), "Should return announcements that are currently active")
        announcement_titles = [a.title for a in result]
        self.assertIn("Currently Active", announcement_titles)
        self.assertIn("Starting Now", announcement_titles)
        self.assertIn("Ending Now", announcement_titles)

    def test_excludes_future_announcements(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        announcement_titles = [a.title for a in result]
        self.assertNotIn("Future Announcement", announcement_titles)

    def test_excludes_past_announcements(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        announcement_titles = [a.title for a in result]
        self.assertNotIn("Past Announcement", announcement_titles)

    def test_orders_by_end_at(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        self.assertEqual(3, result.count())
        # Should be ordered by end_at, so first should be the one ending soonest
        self.assertEqual("Ending Now", result.first().title)

    def test_with_custom_time_in_past(self):
        # Arrange
        past_time = self.two_hours_ago - timedelta(hours=1)  # 3 hours ago, before any announcements

        # Act
        result = self.service.fetch_active_announcements(current_time=past_time)

        # Assert
        self.assertEqual(0, result.count(), "Should return no announcements for time in the past")

    def test_with_custom_time_in_future(self):
        # Arrange
        future_time = self.two_hours_from_now + timedelta(hours=1)  # 3 hours from now, after all announcements

        # Act
        result = self.service.fetch_active_announcements(current_time=future_time)

        # Assert
        self.assertEqual(0, result.count(), "Should return no announcements for time far in the future")

    def test_with_custom_time_matching_future_announcement(self):
        # Arrange
        future_time = self.one_hour_from_now + timedelta(minutes=30)  # In the middle of future announcement

        # Act
        result = self.service.fetch_active_announcements(current_time=future_time)

        # Assert
        self.assertEqual(1, result.count(), "Should return the future announcement when time matches")
        self.assertEqual("Future Announcement", result.first().title)

    def test_uses_current_time_when_not_provided(self):
        # Arrange
        # (Setup is done in the base class)

        # Act
        result = self.service.fetch_active_announcements()

        # Assert
        # This test verifies the method works without explicitly providing current_time
        # The exact count may vary based on timing, but it should execute without error
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'count'))

    def test_returns_empty_queryset_when_no_active_announcements(self):
        # Arrange
        Announcement.objects.all().delete()  # Remove all announcements

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        self.assertEqual(0, result.count(), "Should return empty queryset when no announcements exist")

    def test_ordering_by_end_at_with_different_end_times(self):
        # Arrange
        Announcement.objects.all().delete()  # Clear existing announcements

        # Create announcements with different end times
        Announcement.objects.create(
            title="Ends Soon",
            text="This announcement ends in 30 minutes",
            begin_at=self.one_hour_ago,
            end_at=self.now + timedelta(minutes=30),
        )

        Announcement.objects.create(
            title="Ends Later",
            text="This announcement ends in 2 hours",
            begin_at=self.one_hour_ago,
            end_at=self.now + timedelta(hours=2),
        )

        Announcement.objects.create(
            title="Ends Very Soon",
            text="This announcement ends in 10 minutes",
            begin_at=self.one_hour_ago,
            end_at=self.now + timedelta(minutes=10),
        )

        # Act
        result = self.service.fetch_active_announcements(current_time=self.now)

        # Assert
        self.assertEqual(3, result.count())
        announcements = list(result)
        self.assertEqual("Ends Very Soon", announcements[0].title, "Should be ordered by end_at (earliest first)")
        self.assertEqual("Ends Soon", announcements[1].title)
        self.assertEqual("Ends Later", announcements[2].title) 