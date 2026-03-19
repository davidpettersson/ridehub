from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Announcement


class AnnouncementViewTests(TestCase):
    def test_returns_200(self):
        # Act
        response = self.client.get("/announcements")

        # Assert
        self.assertEqual(response.status_code, 200)

    def test_empty_when_no_announcements(self):
        # Act
        response = self.client.get("/announcements")

        # Assert
        content = response.content.decode().strip()
        self.assertEqual(content, "")

    def test_renders_active_announcement(self):
        # Arrange
        now = timezone.now()
        Announcement.objects.create(
            title="Test Announcement",
            text="<p>Test content</p>",
            type=Announcement.TYPE_INFORMATION,
            begin_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
        )

        # Act
        response = self.client.get("/announcements")

        # Assert
        content = response.content.decode()
        self.assertIn("Test Announcement", content)
        self.assertIn("Test content", content)
        self.assertIn("announcement-info", content)

    def test_renders_warning_announcement(self):
        # Arrange
        now = timezone.now()
        Announcement.objects.create(
            title="Warning",
            text="<p>Watch out</p>",
            type=Announcement.TYPE_WARNING,
            begin_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
        )

        # Act
        response = self.client.get("/announcements")

        # Assert
        content = response.content.decode()
        self.assertIn("announcement-warning", content)

    def test_excludes_expired_announcement(self):
        # Arrange
        now = timezone.now()
        Announcement.objects.create(
            title="Expired",
            text="<p>Old news</p>",
            type=Announcement.TYPE_INFORMATION,
            begin_at=now - timedelta(hours=2),
            end_at=now - timedelta(hours=1),
        )

        # Act
        response = self.client.get("/announcements")

        # Assert
        content = response.content.decode().strip()
        self.assertEqual(content, "")
