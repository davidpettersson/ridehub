from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from backoffice.models import Program, Event


class Command(BaseCommand):
    help = 'Seed test events for development'

    def handle(self, *args, **options):
        programs = self.create_programs()
        self.create_events(programs)
        self.stdout.write(self.style.SUCCESS('Successfully seeded test events'))

    def create_programs(self):
        programs_data = [
            {'name': 'Road Cycling', 'emoji': '🚴', 'color': '#3498db'},
            {'name': 'Mountain Biking', 'emoji': '🚵', 'color': '#27ae60'},
            {'name': 'Gravel Rides', 'emoji': '🛤️', 'color': '#8b4513'},
            {'name': 'Social Events', 'emoji': '🎉', 'color': '#9b59b6'},
            {'name': 'Training', 'emoji': '💪', 'color': '#e74c3c'},
        ]

        programs = {}
        for data in programs_data:
            program, created = Program.objects.get_or_create(
                name=data['name'],
                defaults={'emoji': data['emoji'], 'color': data['color']}
            )
            programs[data['name']] = program
            status = 'Created' if created else 'Found'
            self.stdout.write(f'{status} program: {program.name}')

        return programs

    def create_events(self, programs):
        events_data = [
            # January 2026
            {'name': 'New Year Recovery Ride', 'program': 'Road Cycling', 'day': 1, 'month': 1, 'hour': 10, 'duration': 2, 'location': 'City Park'},
            {'name': 'Winter Training Session', 'program': 'Training', 'day': 4, 'month': 1, 'hour': 9, 'duration': 1.5, 'location': 'Indoor Gym'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 4, 'month': 1, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'MTB Trail Adventure', 'program': 'Mountain Biking', 'day': 5, 'month': 1, 'hour': 9, 'duration': 4, 'location': 'Forest Trailhead'},
            {'name': 'Wednesday Night Social', 'program': 'Social Events', 'day': 8, 'month': 1, 'hour': 18, 'duration': 2, 'location': 'Bike & Brew Pub'},
            {'name': 'Gravel Exploration', 'program': 'Gravel Rides', 'day': 11, 'month': 1, 'hour': 8, 'duration': 5, 'location': 'Rural Route 66'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 11, 'month': 1, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Beginner Road Ride', 'program': 'Road Cycling', 'day': 12, 'month': 1, 'hour': 10, 'duration': 2, 'location': 'Community Center'},
            {'name': 'Indoor Trainer Session', 'program': 'Training', 'day': 15, 'month': 1, 'hour': 18, 'duration': 1, 'location': 'Cycling Studio'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 18, 'month': 1, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'MTB Skills Clinic', 'program': 'Mountain Biking', 'day': 19, 'month': 1, 'hour': 10, 'duration': 3, 'location': 'Skills Park'},
            {'name': 'Club Meeting', 'program': 'Social Events', 'day': 22, 'month': 1, 'hour': 19, 'duration': 2, 'location': 'Community Hall'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 25, 'month': 1, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Long Distance Training', 'program': 'Road Cycling', 'day': 26, 'month': 1, 'hour': 7, 'duration': 5, 'location': 'Highway Rest Stop'},
            {'name': 'Gravel Night Ride', 'program': 'Gravel Rides', 'day': 29, 'month': 1, 'hour': 17, 'duration': 2, 'location': 'Old Mill Road'},

            # February 2026
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 1, 'month': 2, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Super Bowl Party', 'program': 'Social Events', 'day': 1, 'month': 2, 'hour': 17, 'duration': 4, 'location': 'Sports Bar'},
            {'name': 'Winter MTB Challenge', 'program': 'Mountain Biking', 'day': 7, 'month': 2, 'hour': 9, 'duration': 4, 'location': 'Mountain Base'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 8, 'month': 2, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Valentine Couples Ride', 'program': 'Road Cycling', 'day': 14, 'month': 2, 'hour': 10, 'duration': 2, 'location': 'Lakeside Park', 'cancelled': True},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 15, 'month': 2, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Gravel Century Prep', 'program': 'Gravel Rides', 'day': 15, 'month': 2, 'hour': 7, 'duration': 6, 'location': 'Country Store'},
            {'name': 'Presidents Day Ride', 'program': 'Road Cycling', 'day': 16, 'month': 2, 'hour': 9, 'duration': 4, 'location': 'State Capitol'},
            {'name': 'Interval Training', 'program': 'Training', 'day': 18, 'month': 2, 'hour': 18, 'duration': 1.5, 'location': 'Track Stadium'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 22, 'month': 2, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Fat Bike Fun Ride', 'program': 'Mountain Biking', 'day': 22, 'month': 2, 'hour': 11, 'duration': 2, 'location': 'Snow Park'},
            {'name': 'End of Month Social', 'program': 'Social Events', 'day': 27, 'month': 2, 'hour': 18, 'duration': 3, 'location': 'Brewery'},
            {'name': 'Saturday Morning Ride', 'program': 'Road Cycling', 'day': 28, 'month': 2, 'hour': 8, 'duration': 3, 'location': 'Main Street Coffee'},
            {'name': 'Spring Preview Ride', 'program': 'Road Cycling', 'day': 28, 'month': 2, 'hour': 13, 'location': 'Scenic Overlook'},
        ]

        for data in events_data:
            starts_at = timezone.make_aware(
                timezone.datetime(2026, data['month'], data['day'], data['hour'], 0)
            )

            ends_at = None
            if 'duration' in data:
                ends_at = starts_at + timedelta(hours=data['duration'])

            event, created = Event.objects.get_or_create(
                name=data['name'],
                starts_at=starts_at,
                defaults={
                    'program': programs[data['program']],
                    'ends_at': ends_at,
                    'location': data.get('location', ''),
                    'state': Event.STATE_PUBLISHED,
                    'cancelled': data.get('cancelled', False),
                    'description': f"Join us for {data['name']}!",
                }
            )

            status = 'Created' if created else 'Found'
            self.stdout.write(f'{status} event: {event.name} on {starts_at.strftime("%b %d")}')
