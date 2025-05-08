from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from backoffice.models import Event, Program
import datetime
import re


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
    
    def test_ical_feed_timezone_format(self):
        response = self.client.get(reverse('ical_feed'))
        content = response.content.decode('utf-8')
        
        # Check that dates are in the correct UTC format with Z suffix
        date_pattern = re.compile(r'DTSTART:(\d{8}T\d{6}Z)')
        matches = date_pattern.findall(content)
        
        # Ensure we found date patterns
        self.assertTrue(len(matches) > 0, "No properly formatted dates found in iCal feed")
        
        # Check each match has the correct format
        for match in matches:
            # Check that the format is correct (YYYYMMDDTHHMMSSZ)
            self.assertTrue(len(match) == 16, f"Date format incorrect: {match}")
            self.assertTrue(match.endswith('Z'), f"Date not in UTC format: {match}")
        
        # Also check DTEND format
        end_date_pattern = re.compile(r'DTEND:(\d{8}T\d{6}Z)')
        end_matches = end_date_pattern.findall(content)
        self.assertTrue(len(end_matches) > 0, "No properly formatted end dates found in iCal feed")
    
    def test_event_duration_is_one_hour(self):
        response = self.client.get(reverse('ical_feed'))
        content = response.content.decode('utf-8')
        
        # Extract all event blocks from the content
        event_pattern = re.compile(r'BEGIN:VEVENT(.*?)END:VEVENT', re.DOTALL)
        events = event_pattern.findall(content)
        
        for event_content in events:
            # Get start and end times
            start_match = re.search(r'DTSTART:(\d{8}T\d{6}Z)', event_content)
            end_match = re.search(r'DTEND:(\d{8}T\d{6}Z)', event_content)
            
            if start_match and end_match:
                start_time = start_match.group(1)
                end_time = end_match.group(1)
                
                # Convert to datetime objects
                start_dt = datetime.datetime.strptime(start_time, "%Y%m%dT%H%M%SZ")
                end_dt = datetime.datetime.strptime(end_time, "%Y%m%dT%H%M%SZ")
                
                # Calculate the difference
                duration = end_dt - start_dt
                
                # Test that the duration is 1 hour
                self.assertEqual(duration, datetime.timedelta(hours=1),
                                f"Event duration is {duration} but should be 1 hour") 