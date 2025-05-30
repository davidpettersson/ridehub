from datetime import datetime, timezone, timedelta
from django.test import TestCase
from django.template.loader import render_to_string
from django.contrib.auth.models import User
from backoffice.models import Event, Registration, Program
import re


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

    def test_confirmation_email_renders_correctly(self):
        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }
        
        html_content = render_to_string('email/confirmation.html', context)
        
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>Event confirmation</title>', html_content)
        self.assertIn(self.event.name, html_content)
        self.assertIn('Hello!', html_content)
        self.assertIn('Visit profile page', html_content)
        self.assertIn('See you soon!', html_content)
        self.assertIn('Ottawa Bicycle Club', html_content)
        
        # Check that all links are absolute
        self.assert_all_links_absolute(html_content)
        
        # Check specific links
        self.assertIn('href="http://example.com/profile"', html_content)
        
        text_content = render_to_string('email/confirmation.txt', context)
        self.assertIn('Hello!', text_content)
        self.assertIn(self.event.name, text_content)
        # Check that text version also has absolute URLs
        self.assertIn('http://example.com/profile', text_content)

    def test_confirmation_email_with_ride_leader(self):
        self.registration.ride_leader_preference = Registration.RIDE_LEADER_YES
        self.registration.save()
        
        context = {
            'registration': self.registration,
            'base_url': self.base_url
        }
        
        html_content = render_to_string('email/confirmation.html', context)
        self.assertIn('Ride Leader Information:', html_content)
        self.assertIn('Emergency Contact List', html_content)
        
        # Check that all links are absolute
        self.assert_all_links_absolute(html_content)
        
        # Check specific ride leader link
        self.assertIn(f'href="http://example.com/events/{self.event.id}/registrations"', html_content)
        
        text_content = render_to_string('email/confirmation.txt', context)
        self.assertIn('IMPORTANT RIDE LEADER INFORMATION:', text_content)
        # Check that text version also has absolute URL for emergency contact list
        self.assertIn(f'http://example.com/events/{self.event.id}/registrations', text_content)

    def test_login_link_email_renders_correctly(self):
        context = {
            'login_link': 'http://example.com/login/abc123',
            'base_url': self.base_url
        }
        
        html_content = render_to_string('email/login_link.html', context)
        
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>Log in link</title>', html_content)
        self.assertIn('Click here to log in', html_content)
        self.assertIn('Important:', html_content)
        self.assertIn('Ottawa Bicycle Club', html_content)
        # Code block should be rendered with styles from base template
        self.assertIn('<code>', html_content)
        self.assertIn('http://example.com/login/abc123</code>', html_content)
        
        # Check that all links are absolute
        self.assert_all_links_absolute(html_content)
        
        # Check specific links
        self.assertIn('href="http://example.com/login/abc123"', html_content)
        # Check that other links use base_url
        self.assertIn('href="http://example.com/login/"', html_content)
        self.assertIn('href="http://example.com/profile"', html_content)
        
        text_content = render_to_string('email/login_link.txt', context)
        self.assertIn('Hello,', text_content)
        self.assertIn('http://example.com/login/abc123', text_content)

    def test_event_cancelled_email_renders_correctly(self):
        context = {
            'event': self.event,
            'cancellation_reason': 'Bad weather conditions',
            'base_url': self.base_url
        }
        
        html_content = render_to_string('email/event_cancelled.html', context)
        
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>Event cancellation</title>', html_content)
        self.assertIn('Event cancelled:', html_content)
        self.assertIn(self.event.name, html_content)
        self.assertIn('Bad weather conditions', html_content)
        self.assertIn('View other events', html_content)
        self.assertIn('Thank you for your understanding.', html_content)
        self.assertIn('Ottawa Bicycle Club', html_content)
        
        # Check that all links are absolute
        self.assert_all_links_absolute(html_content)
        
        # Check specific link
        self.assertIn('href="http://example.com/events"', html_content)
        
        text_content = render_to_string('email/event_cancelled.txt', context)
        self.assertIn('EVENT CANCELLED:', text_content)
        self.assertIn(self.event.name, text_content)
        # Check that text version also has absolute URL
        self.assertIn('http://example.com/events', text_content)

    def test_base_email_template_structure(self):
        context = {}
        html_content = render_to_string('email/_base_email.html', context)
        
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<meta charset="UTF-8">', html_content)
        self.assertIn('<meta name="viewport"', html_content)
        self.assertIn('font-family: Arial, sans-serif;', html_content)
        self.assertIn('color: #4A6DA7;', html_content)
        self.assertIn('code {', html_content)
        self.assertIn('background-color: #f5f5f5;', html_content)
        self.assertIn('<div class="footer">', html_content)
        self.assertIn('<p>Ottawa Bicycle Club</p>', html_content) 