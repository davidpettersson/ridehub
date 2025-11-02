import csv
import hashlib
import os
from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from backoffice.models import Event, Program, Registration, UserProfile


class ImportStats:
    def __init__(self):
        self.total_rows = 0
        self.skipped_rows = 0
        self.programs_created = 0
        self.events_created = 0
        self.events_existing = 0
        self.users_created = 0
        self.users_existing = 0
        self.registrations_created = 0
        self.registrations_existing = 0

    def increment_total_rows(self):
        self.total_rows += 1

    def increment_skipped_rows(self):
        self.skipped_rows += 1

    def increment_programs(self, created):
        if created:
            self.programs_created += 1

    def increment_events(self, created):
        if created:
            self.events_created += 1
        else:
            self.events_existing += 1

    def increment_users(self, created):
        if created:
            self.users_created += 1
        else:
            self.users_existing += 1

    def increment_registrations(self, created):
        if created:
            self.registrations_created += 1
        else:
            self.registrations_existing += 1

    def print_summary(self, stdout, dry_run):
        from django.core.management.color import color_style
        style = color_style()

        stdout.write('')
        stdout.write('=' * 60)
        stdout.write(style.SUCCESS('Import Summary'))
        stdout.write('=' * 60)
        stdout.write('')
        stdout.write(f'Total rows processed: {self.total_rows}')
        stdout.write(f'Rows skipped (missing data): {self.skipped_rows}')
        stdout.write('')

        if self.programs_created > 0:
            label = '[DRY RUN] Would create' if dry_run else 'Created'
            stdout.write(f'{label} programs: {self.programs_created}')
        stdout.write('')

        if dry_run:
            stdout.write(f'[DRY RUN] Would create events: {self.events_created}')
            stdout.write(f'Events already exist: {self.events_existing}')
            stdout.write('')
            stdout.write(f'[DRY RUN] Would create users: {self.users_created}')
            stdout.write(f'Users already exist: {self.users_existing}')
            stdout.write('')
            stdout.write(f'[DRY RUN] Would create registrations: {self.registrations_created}')
            stdout.write(f'Registrations already exist: {self.registrations_existing}')
        else:
            stdout.write(f'Events created: {self.events_created}')
            stdout.write(f'Events already exist: {self.events_existing}')
            stdout.write('')
            stdout.write(f'Users created: {self.users_created}')
            stdout.write(f'Users already exist: {self.users_existing}')
            stdout.write('')
            stdout.write(f'Registrations created: {self.registrations_created}')
            stdout.write(f'Registrations already exist: {self.registrations_existing}')

        stdout.write('')
        if dry_run:
            stdout.write(style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            stdout.write(style.SUCCESS('Import completed successfully!'))


class ImportOperations:
    def __init__(self):
        self.programs = []
        self.events = []
        self.users = []
        self.user_profile_data = []
        self.registrations = []
        self.stats = ImportStats()

    def add_program(self, program):
        self.programs.append(program)
        self.stats.increment_programs(True)

    def add_event(self, event, existing=False):
        if not existing:
            self.events.append(event)
        self.stats.increment_events(not existing)

    def add_user(self, user, existing=False):
        if not existing:
            self.users.append(user)
        self.stats.increment_users(not existing)

    def add_user_profile_data(self, user, profile_data):
        self.user_profile_data.append((user, profile_data))

    def add_registration(self, registration, existing=False):
        if not existing:
            self.registrations.append(registration)
        self.stats.increment_registrations(not existing)

    def save_all(self):
        for program in self.programs:
            program.save()
        for event in self.events:
            event.save()
        for user in self.users:
            user.save()
        for user, profile_data in self.user_profile_data:
            profile = user.profile
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        for registration in self.registrations:
            registration.save()


class Command(BaseCommand):
    help = 'Import legacy registrations from WebScorer CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save to database, just print what would be imported',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print additional debug information',
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.dry_run = options['dry_run']
        self.debug = options['debug']

        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file_path}'))
            return

        self.stdout.write('Processing CSV file: {}'.format(csv_file_path))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        self.operations = ImportOperations()
        self.program = None
        self.process_csv(csv_file_path)

        if not self.dry_run:
            self.save_operations()

        self.print_summary()

    def save_operations(self):
        from django.db import transaction

        with transaction.atomic():
            self.operations.save_all()

    def process_csv(self, csv_file_path):
        events_cache = {}
        users_cache = {}

        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter='\t')

            if self.debug:
                self.stdout.write(f"CSV headers: {csv_reader.fieldnames}")
                self.stdout.write('')

            for row in csv_reader:
                self.operations.stats.increment_total_rows()

                event = self.ensure_event(row, events_cache)
                if not event:
                    self.operations.stats.increment_skipped_rows()
                    continue

                user = self.ensure_user(row, users_cache)
                if not user:
                    self.operations.stats.increment_skipped_rows()
                    continue

                self.create_registration(row, event, user)

    def ensure_program(self):
        if self.program:
            return self.program

        program_name = 'Legacy'

        existing = Program.objects.filter(name=program_name).first()
        if existing:
            self.program = existing
            return self.program

        self.program = Program(name=program_name)
        self.operations.add_program(self.program)

        if self.debug:
            label = '[DRY RUN] Would create' if self.dry_run else 'Creating'
            self.stdout.write(self.style.SUCCESS(f'{label} Program: "{program_name}"'))

        return self.program

    def ensure_event(self, row, events_cache):
        event_name = row.get('Event name', '').strip()
        event_date_str = row.get('Event date', '').strip()
        event_id = row.get('Event id', '').strip()

        if not event_name or not event_date_str or not event_id:
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with missing event data: {event_name}'
                ))
            return None

        cache_key = f"{event_id}_{event_name}_{event_date_str}"
        if cache_key in events_cache:
            return events_cache[cache_key]

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Invalid date format: {event_date_str}'
                ))
            return None

        existing = Event.objects.filter(legacy_event_id=event_id).first()
        if existing:
            self.operations.add_event(existing, existing=True)
            events_cache[cache_key] = existing
            return existing

        program = self.ensure_program()
        starts_at = timezone.make_aware(
            datetime.combine(event_date, datetime.min.time().replace(hour=9))
        )
        ends_at = timezone.make_aware(
            datetime.combine(event_date, datetime.min.time().replace(hour=12))
        )
        registration_closes_at = starts_at

        event = Event(
            program=program,
            name=event_name,
            starts_at=starts_at,
            ends_at=ends_at,
            registration_closes_at=registration_closes_at,
            description='Legacy event imported from WebScorer',
            legacy=True,
            legacy_event_id=event_id,
            visible=False,
            archived=True,
            archived_at=timezone.now(),
        )
        self.operations.add_event(event, existing=False)
        events_cache[cache_key] = event

        if self.debug:
            label = '[DRY RUN] Would create' if self.dry_run else 'Creating'
            self.stdout.write(self.style.SUCCESS(
                f'{label} event: {event_name} ({event_date}) [ID: {event_id}]'
            ))

        return event

    def ensure_user(self, row, users_cache):
        email = row.get('Email', '').strip().lower()
        first_name = row.get('First name', '').strip()
        last_name = row.get('Last name', '').strip()
        phone = row.get('Phone #', '').strip()
        gender = row.get('Gender', '').strip()

        if not email or not first_name or not last_name:
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with missing user data: {email}'
                ))
            return None

        if email in users_cache:
            return users_cache[email]

        existing = User.objects.filter(email=email).first()
        if existing:
            self.operations.add_user(existing, existing=True)
            users_cache[email] = existing
            return existing

        username = email
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{email}_{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_unusable_password()
        self.operations.add_user(user, existing=False)

        gender_identity = self.parse_gender(gender)
        profile_data = {
            'phone': phone,
            'gender_identity': gender_identity,
            'legacy': True,
        }
        self.operations.add_user_profile_data(user, profile_data)

        users_cache[email] = user

        if self.debug:
            label = '[DRY RUN] Would create' if self.dry_run else 'Creating'
            self.stdout.write(self.style.SUCCESS(
                f'{label} user: {first_name} {last_name} ({email})'
            ))

        return user

    def create_registration(self, row, event, user):
        name = row.get('Name', '').strip()
        first_name = row.get('First name', '').strip()
        last_name = row.get('Last name', '').strip()
        email = row.get('Email', '').strip().lower()
        phone = row.get('Phone #', '').strip()
        emergency_contact_name = row.get('Emergency contact name', '').strip()
        emergency_contact_phone = row.get('Emergency contact phone #', '').strip()
        registration_time_str = row.get('Registration time', '').strip()
        event_id = row.get('Event id', '').strip()

        try:
            submitted_at = datetime.strptime(registration_time_str, '%b %d, %Y at %I:%M %p')
            submitted_at = timezone.make_aware(submitted_at)
        except (ValueError, TypeError):
            submitted_at = timezone.now()

        legacy_reg_id = self.generate_legacy_registration_id(event_id, email, submitted_at)

        existing_registration = Registration.objects.filter(
            legacy_registration_id=legacy_reg_id
        ).first()
        if existing_registration:
            self.operations.add_registration(existing_registration, existing=True)
            if self.debug:
                event_name = event.name if hasattr(event, 'name') else event_id
                self.stdout.write(
                    f'Registration already exists: {name} -> {event_name}'
                )
            return

        ride_leader_preference = self.parse_ride_leader(row)

        registration = Registration(
            name=name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            event=event,
            user=user,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            ride_leader_preference=ride_leader_preference,
            state=Registration.STATE_CONFIRMED,
            submitted_at=submitted_at,
            confirmed_at=submitted_at,
            legacy=True,
            legacy_registration_id=legacy_reg_id,
        )
        self.operations.add_registration(registration, existing=False)

        if self.debug:
            label = '[DRY RUN] Would create' if self.dry_run else 'Creating'
            event_name = event.name if hasattr(event, 'name') else event_id
            self.stdout.write(
                f'{label} registration: {name} -> {event_name}'
            )

    def generate_legacy_registration_id(self, event_id, email, submitted_at):
        composite_key = f"{event_id}_{email}_{submitted_at.isoformat()}"
        return hashlib.sha256(composite_key.encode()).hexdigest()

    def parse_gender(self, gender):
        gender_lower = gender.lower()
        if 'female' in gender_lower or 'woman' in gender_lower:
            return UserProfile.GenderIdentity.WOMAN
        elif 'male' in gender_lower or 'man' in gender_lower:
            return UserProfile.GenderIdentity.MAN
        else:
            return UserProfile.GenderIdentity.NOT_PROVIDED

    def parse_ride_leader(self, row):
        wave = row.get('Wave', '').strip().lower()
        if wave:
            if 'lead' in wave or 'leader' in wave:
                return Registration.RideLeaderPreference.YES
            elif 'ride in' in wave or 'rider in' in wave or 'follow' in wave:
                return Registration.RideLeaderPreference.NO

        ride_leader_columns = [
            'Ride leader',
            'Are you willing to  be a ride leader?',
            'Are you willing to be a ride leader?',
        ]

        for col_name in ride_leader_columns:
            value = row.get(col_name, '').strip().upper()
            if value in ['Y', 'YES']:
                return Registration.RideLeaderPreference.YES
            elif value in ['N', 'NO']:
                return Registration.RideLeaderPreference.NO

        return Registration.RideLeaderPreference.NOT_APPLICABLE

    def print_summary(self):
        self.operations.stats.print_summary(self.stdout, self.dry_run)
