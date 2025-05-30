import re
from datetime import datetime, timezone, timedelta

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase

from backoffice.models import Event, Registration, Program


class TestEmailTemplates(TestCase):
    def setUp(self):
        self.base_url = "http://example.com"
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
            registration_closes_at=event_start - timedelta(hours=1),  # Registration closes 1 hour before event
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

    def assert_all_links_absolute(self, html_content):
        """Assert that all href links in the HTML are absolute URLs."""
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

    def test_confirmation_email_contains_key_information(self):
        """Test that confirmation email contains essential event information."""
        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

        html_content = render_to_string('email/confirmation.html', context)
        self.assertIn(self.event.name, html_content)
        self.assertIn('profile', html_content.lower())

        text_content = render_to_string('email/confirmation.txt', context)
        self.assertIn(self.event.name, text_content)

    def test_confirmation_email_links_are_absolute(self):
        """Test that all links in confirmation email are absolute URLs."""
        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

        html_content = render_to_string('email/confirmation.html', context)
        self.assert_all_links_absolute(html_content)

        # Verify profile link exists and is absolute
        self.assertRegex(html_content, r'href="http[s]?://[^"]*profile[^"]*"')

    def test_confirmation_email_text_version_has_absolute_urls(self):
        """Test that text version of confirmation email has absolute URLs."""
        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

        text_content = render_to_string('email/confirmation.txt', context)

        # Check that URLs in text are absolute
        url_pattern = re.compile(r'http[s]?://[^\s]+')
        urls = url_pattern.findall(text_content)
        self.assertGreater(len(urls), 0, "Text email should contain at least one URL")

        # Verify profile URL is present
        self.assertRegex(text_content, r'http[s]?://[^\s]*profile')

    def test_ride_leader_confirmation_includes_emergency_contact_link(self):
        """Test that ride leader confirmation includes emergency contact list link."""
        self.registration.ride_leader_preference = Registration.RIDE_LEADER_YES
        self.registration.save()

        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

        html_content = render_to_string('email/confirmation.html', context)

        # Check for ride leader content without being specific about wording
        self.assertIn('ride leader', html_content.lower())
        self.assertIn('emergency', html_content.lower())

        # Verify emergency contact link exists and is absolute
        self.assertRegex(html_content, rf'href="http[s]?://[^"]*events/{self.event.id}/registrations[^"]*"')

    def test_ride_leader_confirmation_text_includes_emergency_contact_link(self):
        """Test that ride leader text confirmation includes emergency contact list link."""
        self.registration.ride_leader_preference = Registration.RIDE_LEADER_YES
        self.registration.save()

        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }

        text_content = render_to_string('email/confirmation.txt', context)

        # Check for ride leader content
        self.assertIn('ride leader', text_content.lower())

        # Verify emergency contact URL is present
        self.assertIn(f'{self.base_url}/events/{self.event.id}/registrations', text_content)

    def test_login_link_email_contains_link(self):
        """Test that login link email contains the actual login link."""
        login_link = 'http://example.com/login/abc123'
        context = {
            'login_link': login_link,
            'base_url': self.base_url
        }

        html_content = render_to_string('email/login_link.html', context)

        # Verify login link is present in href
        self.assertIn(f'href="{login_link}"', html_content)

        text_content = render_to_string('email/login_link.txt', context)
        self.assertIn(login_link, text_content)

    def test_login_link_email_has_valid_structure(self):
        """Test that login link email has proper HTML structure."""
        context = {
            'login_link': 'http://example.com/login/abc123',
            'base_url': self.base_url
        }

        html_content = render_to_string('email/login_link.html', context)

        # Check basic HTML structure
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>', html_content)
        self.assertIn('</title>', html_content)

    def test_login_link_email_links_are_absolute(self):
        """Test that all links in login link email are absolute URLs."""
        context = {
            'login_link': 'http://example.com/login/abc123',
            'base_url': self.base_url
        }

        html_content = render_to_string('email/login_link.html', context)
        self.assert_all_links_absolute(html_content)

    def test_event_cancelled_email_contains_event_name(self):
        """Test that cancellation email contains the event name."""
        context = {
            'event': self.event,
            'cancellation_reason': 'Bad weather conditions',
            'base_url': self.base_url
        }

        html_content = render_to_string('email/event_cancelled.html', context)
        self.assertIn(self.event.name, html_content)

        text_content = render_to_string('email/event_cancelled.txt', context)
        self.assertIn(self.event.name, text_content)

    def test_event_cancelled_email_contains_cancellation_reason(self):
        """Test that cancellation email contains the cancellation reason."""
        reason = 'Bad weather conditions'
        context = {
            'event': self.event,
            'cancellation_reason': reason,
            'base_url': self.base_url
        }

        html_content = render_to_string('email/event_cancelled.html', context)
        self.assertIn(reason, html_content)

        text_content = render_to_string('email/event_cancelled.txt', context)
        self.assertIn(reason, text_content)

    def test_event_cancelled_email_links_are_absolute(self):
        """Test that all links in cancellation email are absolute URLs."""
        context = {
            'event': self.event,
            'cancellation_reason': 'Bad weather conditions',
            'base_url': self.base_url
        }

        html_content = render_to_string('email/event_cancelled.html', context)
        self.assert_all_links_absolute(html_content)

        # Verify events link exists and is absolute
        self.assertRegex(html_content, r'href="http[s]?://[^"]*events[^"]*"')

    def test_event_cancelled_text_email_has_absolute_urls(self):
        """Test that text version of cancellation email has absolute URLs."""
        context = {
            'event': self.event,
            'cancellation_reason': 'Bad weather conditions',
            'base_url': self.base_url
        }

        text_content = render_to_string('email/event_cancelled.txt', context)

        # Verify events URL is present
        self.assertIn(f'{self.base_url}/events', text_content)

    def test_base_email_template_has_required_meta_tags(self):
        """Test that base email template has required meta tags."""
        context = {}
        html_content = render_to_string('email/_base_email.html', context)

        # Check for essential meta tags
        self.assertIn('<meta charset="UTF-8">', html_content)
        self.assertIn('<meta name="viewport"', html_content)

    def test_base_email_template_has_footer(self):
        """Test that base email template includes a footer."""
        context = {}
        html_content = render_to_string('email/_base_email.html', context)

        # Check for footer presence without being specific about class names
        self.assertIn('footer', html_content.lower())
        self.assertIn('Ottawa Bicycle Club', html_content)
