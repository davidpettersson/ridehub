import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from backoffice.models import Program, Event, Route, Ride, SpeedRange, Registration


FIRST_NAMES = [
    'Alice', 'Bob', 'Charlie', 'Diana', 'Edward', 'Fiona', 'George', 'Hannah',
    'Ivan', 'Julia', 'Kevin', 'Laura', 'Michael', 'Nadia', 'Oscar', 'Patricia',
    'Quentin', 'Rachel', 'Samuel', 'Tanya', 'Ulrich', 'Vera', 'Walter', 'Xena',
    'Yusuf', 'Zara', 'Andre', 'Brigitte', 'Claude', 'Dominique',
]

LAST_NAMES = [
    'Anderson', 'Brown', 'Campbell', 'Davis', 'Evans', 'Fisher', 'Garcia',
    'Harris', 'Ibrahim', 'Johnson', 'Kim', 'Lavoie', 'Martin', 'Nguyen',
    'Ouellet', 'Patel', 'Quinn', 'Robinson', 'Smith', 'Tremblay',
    'Underwood', 'Vasquez', 'Williams', 'Xu', 'Young', 'Zhang',
]

LOCATIONS = [
    'Andrew Haydon Park', 'Mooney\'s Bay', 'Britannia Beach', 'Dow\'s Lake Pavilion',
    'Hog\'s Back Falls', 'Kanata Recreation Complex', 'Terry Fox Athletic Facility',
]

EVENT_TEMPLATES = [
    {
        'name': 'Saturday Morning Ride',
        'program': 'Road Cycling',
        'hour': 8,
        'duration': 3,
        'rides': [
            ('A Ride', 'Long Loop', ['30-35', '35+']),
            ('B Ride', 'Medium Loop', ['25-30', '30-35']),
            ('C Ride', 'Short Loop', ['20-25', '25-30']),
        ],
    },
    {
        'name': 'Gravel Explorer',
        'program': 'Gravel Rides',
        'hour': 9,
        'duration': 4,
        'rides': [
            ('Gravel Route', 'Gravel Adventure', ['20-25', '25-30']),
        ],
    },
    {
        'name': 'Mountain Bike Trail Ride',
        'program': 'Mountain Biking',
        'hour': 9,
        'duration': 3,
        'rides': [
            ('Trail Ride', 'MTB Trail Loop', ['20-25']),
        ],
    },
    {
        'name': 'Interval Training',
        'program': 'Training',
        'hour': 18,
        'duration': 1,
    },
    {
        'name': 'Long Distance Training',
        'program': 'Road Cycling',
        'hour': 7,
        'duration': 5,
        'rides': [
            ('Century Route', 'Century Route', ['30-35', '35+']),
            ('Metric Century', 'Metric Century', ['25-30', '30-35']),
        ],
    },
    {
        'name': 'Recovery Spin',
        'program': 'Road Cycling',
        'hour': 10,
        'duration': 2,
        'rides': [
            ('Easy Ride', 'Recovery Spin', ['20-25']),
        ],
    },
    {
        'name': 'Social Ride and Coffee',
        'program': 'Social Events',
        'hour': 10,
        'duration': 2,
    },
]


class Command(BaseCommand):
    help = 'Seed test events for development. Creates 7 events (one per day for the next week) with rides, speed ranges, users, and registrations.'

    def handle(self, *args, **options):
        programs = self._create_programs()
        routes = self._create_routes()
        speed_ranges = self._create_speed_ranges()
        users = self._create_users()
        self._create_events(programs, routes, speed_ranges, users)
        self.stdout.write(self.style.SUCCESS('Successfully seeded test events'))

    def _create_programs(self):
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
            if created:
                self.stdout.write(f'  Created program: {program.name}')

        return programs

    def _create_routes(self):
        routes_data = [
            {'name': 'Short Loop', 'distance': 25},
            {'name': 'Medium Loop', 'distance': 50},
            {'name': 'Long Loop', 'distance': 80},
            {'name': 'Century Route', 'distance': 100},
            {'name': 'Metric Century', 'distance': 100},
            {'name': 'Recovery Spin', 'distance': 30},
            {'name': 'Gravel Adventure', 'distance': 60},
            {'name': 'MTB Trail Loop', 'distance': 20},
        ]

        routes = {}
        for data in routes_data:
            route, created = Route.objects.get_or_create(
                name=data['name'],
                defaults={'distance': data['distance']}
            )
            routes[data['name']] = route
            if created:
                self.stdout.write(f'  Created route: {route.name} ({route.distance} km)')

        return routes

    def _create_speed_ranges(self):
        ranges_data = [
            {'lower_limit': 20, 'upper_limit': 25},
            {'lower_limit': 25, 'upper_limit': 30},
            {'lower_limit': 30, 'upper_limit': 35},
            {'lower_limit': 35, 'upper_limit': None},
        ]

        speed_ranges = {}
        for data in ranges_data:
            sr, created = SpeedRange.objects.get_or_create(
                lower_limit=data['lower_limit'],
                upper_limit=data['upper_limit'],
            )
            key = f"{data['lower_limit']}-{data['upper_limit']}" if data['upper_limit'] else f"{data['lower_limit']}+"
            speed_ranges[key] = sr
            if created:
                self.stdout.write(f'  Created speed range: {sr}')

        return speed_ranges

    def _create_users(self):
        users = []
        for first_name, last_name in zip(FIRST_NAMES, LAST_NAMES):
            email = f'{first_name.lower()}.{last_name.lower()}@example.com'
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            if created:
                user.set_unusable_password()
                user.save()
                user.profile.phone = f'+1613555{random.randint(1000, 9999)}'
                user.profile.save()
            users.append(user)

        self.stdout.write(f'  Ensured {len(users)} test users exist')
        return users

    def _create_events(self, programs, routes, speed_ranges, users):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        for day_offset in range(1, 8):
            template = EVENT_TEMPLATES[day_offset % len(EVENT_TEMPLATES)]
            event_date = today_start + timedelta(days=day_offset)
            starts_at = event_date.replace(hour=template['hour'])
            ends_at = starts_at + timedelta(hours=template['duration'])
            registration_closes_at = starts_at - timedelta(hours=12)

            has_rides = 'rides' in template
            location = random.choice(LOCATIONS)
            state = Event.STATE_ANNOUNCED if day_offset >= 6 else Event.STATE_LIVE

            event, created = Event.objects.get_or_create(
                name=f"{template['name']} — {starts_at.strftime('%b %d')}",
                starts_at=starts_at,
                defaults={
                    'program': programs[template['program']],
                    'ends_at': ends_at,
                    'registration_closes_at': registration_closes_at,
                    'location': location,
                    'state': state,
                    'description': f"Join us for {template['name']}!",
                    'ride_leaders_wanted': has_rides,
                    'requires_emergency_contact': has_rides,
                    'requires_membership': False,
                }
            )

            if not created:
                self.stdout.write(f'  Skipped existing event: {event.name}')
                continue

            self.stdout.write(f'  Created event: {event.name} at {location}')

            rides = []
            if has_rides:
                for idx, (ride_name, route_name, sr_keys) in enumerate(template['rides']):
                    ride = Ride.objects.create(
                        event=event,
                        name=ride_name,
                        route=routes[route_name],
                        ordering=idx,
                    )
                    for sr_key in sr_keys:
                        ride.speed_ranges.add(speed_ranges[sr_key])
                    rides.append(ride)
                    self.stdout.write(f'    Ride: {ride.name} ({routes[route_name].distance} km) — speeds: {", ".join(sr_keys)}')

            num_registrations = random.randint(5, min(15, len(users)))
            selected_users = random.sample(users, num_registrations)

            for user in selected_users:
                ride = None
                speed_range = None
                ride_leader_pref = Registration.RideLeaderPreference.NOT_APPLICABLE
                emergency_name = ''
                emergency_phone = ''

                if rides:
                    ride = random.choice(rides)
                    available_speeds = list(ride.speed_ranges.all())
                    if available_speeds:
                        speed_range = random.choice(available_speeds)
                    ride_leader_pref = random.choices(
                        [Registration.RideLeaderPreference.YES, Registration.RideLeaderPreference.NO],
                        weights=[1, 4],
                    )[0]

                if event.requires_emergency_contact:
                    emergency_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
                    emergency_phone = f'+1613555{random.randint(1000, 9999)}'

                reg = Registration.objects.create(
                    event=event,
                    user=user,
                    name=user.get_full_name(),
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=user.email,
                    phone=user.profile.phone,
                    ride=ride,
                    speed_range_preference=speed_range,
                    ride_leader_preference=ride_leader_pref,
                    emergency_contact_name=emergency_name,
                    emergency_contact_phone=emergency_phone,
                )
                reg.confirm()
                reg.save()

            self.stdout.write(f'    Registered {num_registrations} riders')
