import re
from datetime import datetime, timezone, timedelta

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from backoffice.models import Event, Registration, Program


class BaseEmailTestCase(TestCase):

    def setUp(self):
        self.base_url = "http://example.com"
    
    def assert_all_links_absolute(self, html_content):
        # Find all href attributes
        href_pattern = re.compile(r'href="([^"]+)"')
        links = href_pattern.findall(html_content)

        for link in links:
            # Skip mailto links
            if link.startswith('mailto:'):
                continue

            # Assert that the link is absolute (starts with http:// or https://)
            self.assertTrue(
                link.startswith('http://') or link.startswith('https://'),
                f"Link '{link}' is not an absolute URL"
            )

            # Assert that the link doesn't start with just /
            self.assertFalse(
                link.startswith('/') and not link.startswith('//'),
                f"Link '{link}' appears to be a relative URL"
            )
    
    def assert_text_contains_absolute_urls(self, text_content):
        url_pattern = re.compile(r'http[s]?://[^\s]+')
        urls = url_pattern.findall(text_content)
        self.assertGreater(len(urls), 0, "Text email should contain at least one URL")
        return urls


class TestConfirmationEmail(BaseEmailTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.program = Program.objects.create(name="Test Program")

        # Create event with all required fields
        event_start = datetime(2024, 12, 25, 10, 0, tzinfo=timezone.utc)
        self.event = Event.objects.create(
            name="Test Event",
            starts_at=event_start,
            registration_closes_at=event_start - timedelta(hours=1),
            program=self.program,
            location="Test Location",
            description="Test Description"
        )
        self.registration = Registration.objects.create(
            event=self.event,
            user=self.user,
            name=f"{self.user.first_name} {self.user.last_name}",
            email=self.user.email,
            ride_leader_preference=Registration.RIDE_LEADER_NO
        )
        self.context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

    def test_contains_key_information(self):
        html_content = render_to_string('email/confirmation.html', self.context)
        self.assertIn(self.event.name, html_content)
        self.assertIn('profile', html_content.lower())

        text_content = render_to_string('email/confirmation.txt', self.context)
        self.assertIn(self.event.name, text_content)

    def test_links_are_absolute(self):
        html_content = render_to_string('email/confirmation.html', self.context)
        self.assert_all_links_absolute(html_content)

        # Verify profile link exists and is absolute
        self.assertRegex(html_content, r'href="http[s]?://[^"]*profile[^"]*"')

    def test_text_version_has_absolute_urls(self):
        text_content = render_to_string('email/confirmation.txt', self.context)
        
        # Check that URLs in text are absolute
        self.assert_text_contains_absolute_urls(text_content)

        # Verify profile URL is present
        self.assertRegex(text_content, r'http[s]?://[^\s]*profile')

    def test_ride_leader_includes_emergency_contact_link(self):
        self.registration.ride_leader_preference = Registration.RIDE_LEADER_YES
        self.registration.save()

        html_content = render_to_string('email/confirmation.html', self.context)

        # Check for ride leader content without being specific about wording
        self.assertIn('ride leader', html_content.lower())
        self.assertIn('emergency', html_content.lower())

        # Verify emergency contact link exists and is absolute
        emergency_url = f"{self.base_url}{reverse('riders_list', kwargs={'event_id': self.event.id})}"
        self.assertRegex(html_content, rf'href="{re.escape(emergency_url)}"')

    def test_ride_leader_text_includes_emergency_contact_link(self):
        self.registration.ride_leader_preference = Registration.RIDE_LEADER_YES
        self.registration.save()

        text_content = render_to_string('email/confirmation.txt', self.context)

        # Check for ride leader content
        self.assertIn('ride leader', text_content.lower())

        # Verify emergency contact URL is present
        emergency_url = f"{self.base_url}{reverse('riders_list', kwargs={'event_id': self.event.id})}"
        self.assertIn(emergency_url, text_content)


class TestLoginLinkEmail(BaseEmailTestCase):
    def setUp(self):
        super().setUp()
        self.login_link = 'http://example.com/login/abc123'
        self.context = {
            'login_link': self.login_link,
            'base_url': self.base_url
        }

    def test_contains_login_link(self):
        html_content = render_to_string('email/login_link.html', self.context)

        # Verify login link is present in href
        self.assertIn(f'href="{self.login_link}"', html_content)

        text_content = render_to_string('email/login_link.txt', self.context)
        self.assertIn(self.login_link, text_content)

    def test_has_valid_html_structure(self):
        html_content = render_to_string('email/login_link.html', self.context)

        # Check basic HTML structure
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>', html_content)
        self.assertIn('</title>', html_content)

    def test_links_are_absolute(self):
        html_content = render_to_string('email/login_link.html', self.context)
        self.assert_all_links_absolute(html_content)


class TestEventCancelledEmail(BaseEmailTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com'
        )
        self.program = Program.objects.create(name="Test Program")
        
        event_start = datetime(2024, 12, 25, 10, 0, tzinfo=timezone.utc)
        self.event = Event.objects.create(
            name="Cancelled Event",
            starts_at=event_start,
            registration_closes_at=event_start - timedelta(hours=1),
            program=self.program,
            location="Test Location",
            description="Test Description"
        )
        self.cancellation_reason = 'Bad weather conditions'
        self.context = {
            'event': self.event,
            'cancellation_reason': self.cancellation_reason,
            'base_url': self.base_url
        }

    def test_contains_event_name(self):
        html_content = render_to_string('email/event_cancelled.html', self.context)
        self.assertIn(self.event.name, html_content)

        text_content = render_to_string('email/event_cancelled.txt', self.context)
        self.assertIn(self.event.name, text_content)

    def test_contains_cancellation_reason(self):
        html_content = render_to_string('email/event_cancelled.html', self.context)
        self.assertIn(self.cancellation_reason, html_content)

        text_content = render_to_string('email/event_cancelled.txt', self.context)
        self.assertIn(self.cancellation_reason, text_content)

    def test_links_are_absolute(self):
        html_content = render_to_string('email/event_cancelled.html', self.context)
        self.assert_all_links_absolute(html_content)

        # Verify events link exists and is absolute
        events_url = f"{self.base_url}{reverse('event_list')}"
        self.assertRegex(html_content, rf'href="{re.escape(events_url)}"')

    def test_text_version_has_absolute_urls(self):
        text_content = render_to_string('email/event_cancelled.txt', self.context)

        # Verify events URL is present
        events_url = f"{self.base_url}{reverse('event_list')}"
        self.assertIn(events_url, text_content)
