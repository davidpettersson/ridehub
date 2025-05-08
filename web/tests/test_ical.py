from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from backoffice.models import Event, Program
import datetime


class ICalFeedTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create a program
        self.program = Program.objects.create(name="Test Program")
        
        # Create a future event
        self.future_event = Event.objects.create(
            program=self.program,
            name="Future Event",
            starts_at=timezone.now() + datetime.timedelta(days=7),
            registration_closes_at=timezone.now() + datetime.timedelta(days=6),
            description="This is a future event"
        )
        
        # Create a cancelled event
        self.cancelled_event = Event.objects.create(
            program=self.program,
            name="Cancelled Event",
            starts_at=timezone.now() + datetime.timedelta(days=14),
            registration_closes_at=timezone.now() + datetime.timedelta(days=13),
            description="This is a cancelled event",
            cancelled=True,
            cancelled_at=timezone.now(),
            cancellation_reason="Weather conditions"
        )
        
        # Create a past event
        self.past_event = Event.objects.create(
            program=self.program,
            name="Past Event",
            starts_at=timezone.now() - datetime.timedelta(days=7),
            registration_closes_at=timezone.now() - datetime.timedelta(days=8),
            description="This is a past event"
        )
    
    def test_ical_feed_contains_all_events(self):
        response = self.client.get(reverse('ical_feed'))
        
        # Test response basics
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=ridehub_events.ics')
        
        # Convert response content to string for easier checking
        content = response.content.decode('utf-8')
        
        # Check that the calendar structure is correct
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertIn('VERSION:2.0', content)
        self.assertIn('END:VCALENDAR', content)
        
        # Check all events are included
        self.assertIn(f'SUMMARY:{self.future_event.name}', content)
        self.assertIn(f'SUMMARY:{self.cancelled_event.name}', content)
        self.assertIn(f'SUMMARY:{self.past_event.name}', content)
        
        # Check cancelled status
        self.assertIn('STATUS:CANCELLED', content)
        self.assertIn('STATUS:CONFIRMED', content)
        
        # Check UID formatting
        self.assertIn(f'UID:{self.future_event.id}@ridehub', content)
        
        # Count the number of events
        self.assertEqual(content.count('BEGIN:VEVENT'), 3)
        self.assertEqual(content.count('END:VEVENT'), 3) 