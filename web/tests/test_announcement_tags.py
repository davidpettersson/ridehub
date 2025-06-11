from datetime import timedelta

from django.test import TestCase
from django.template import Context, Template
from django.utils import timezone

from backoffice.models import Announcement


class AnnouncementTagsTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.one_hour_ago = self.now - timedelta(hours=1)
        self.one_hour_from_now = self.now + timedelta(hours=1)

    def test_active_announcements_tag_renders_active_announcements(self):
        # Arrange
        Announcement.objects.create(
            title="Test Announcement",
            text="This is a test announcement",
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("Test Announcement", rendered)
        self.assertIn("This is a test announcement", rendered)
        self.assertIn("bg-blue-50", rendered)

    def test_active_announcements_tag_excludes_inactive_announcements(self):
        # Arrange
        Announcement.objects.create(
            title="Past Announcement",
            text="This announcement is in the past",
            begin_at=self.now - timedelta(hours=2),
            end_at=self.one_hour_ago,
        )

        Announcement.objects.create(
            title="Future Announcement",
            text="This announcement is in the future",
            begin_at=self.one_hour_from_now,
            end_at=self.now + timedelta(hours=2),
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertNotIn("This announcement is in the past", rendered)
        self.assertNotIn("This announcement is in the future", rendered)

    def test_active_announcements_tag_renders_multiple_announcements(self):
        # Arrange
        Announcement.objects.create(
            title="First Announcement",
            text="First announcement text",
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        Announcement.objects.create(
            title="Second Announcement",
            text="Second announcement text",
            begin_at=self.now - timedelta(minutes=30),
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("First Announcement", rendered)
        self.assertIn("First announcement text", rendered)
        self.assertIn("Second Announcement", rendered)
        self.assertIn("Second announcement text", rendered)

    def test_active_announcements_tag_renders_nothing_when_no_announcements(self):
        # Arrange
        # No announcements created

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertEqual(rendered.strip(), "")

    def test_active_announcements_tag_renders_html_content_safely(self):
        # Arrange
        Announcement.objects.create(
            title="HTML Announcement",
            text="<strong>Bold text</strong> and <em>italic text</em>",
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("HTML Announcement", rendered)
        self.assertIn("<strong>Bold text</strong>", rendered)
        self.assertIn("<em>italic text</em>", rendered)

    def test_information_announcement_has_blue_styling(self):
        # Arrange
        Announcement.objects.create(
            title="Information Announcement",
            text="This is an information announcement",
            type=Announcement.TYPE_INFORMATION,
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("bg-blue-50", rendered)
        self.assertIn("border-blue-400", rendered)
        self.assertIn("text-blue-900", rendered)
        self.assertIn("text-blue-800", rendered)

    def test_warning_announcement_has_yellow_styling(self):
        # Arrange
        Announcement.objects.create(
            title="Warning Announcement",
            text="This is a warning announcement", 
            type=Announcement.TYPE_WARNING,
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("bg-yellow-50", rendered)
        self.assertIn("border-yellow-400", rendered)
        self.assertIn("text-yellow-900", rendered)
        self.assertIn("text-yellow-800", rendered)

    def test_mixed_announcement_types_render_correctly(self):
        # Arrange
        Announcement.objects.create(
            title="Info",
            text="Information text",
            type=Announcement.TYPE_INFORMATION,
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        Announcement.objects.create(
            title="Warning",
            text="Warning text",
            type=Announcement.TYPE_WARNING,
            begin_at=self.one_hour_ago,
            end_at=self.one_hour_from_now,
        )

        template = Template("{% load announcement_tags %}{% active_announcements %}")

        # Act
        rendered = template.render(Context())

        # Assert
        self.assertIn("bg-blue-50", rendered)
        self.assertIn("bg-yellow-50", rendered)
        self.assertIn("Information text", rendered)
        self.assertIn("Warning text", rendered) 