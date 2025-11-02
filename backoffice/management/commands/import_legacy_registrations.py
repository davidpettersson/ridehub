import csv
import hashlib
import os
from datetime import datetime
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from backoffice.models import Event, Program, Registration, UserProfile


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

        stats = self.process_csv(csv_file_path)
        self.print_summary(stats)

    def process_csv(self, csv_file_path):
        stats = {
            'total_rows': 0,
            'skipped_rows': 0,
            'programs_created': 0,
            'events_created': 0,
            'events_existing': 0,
            'users_created': 0,
            'users_existing': 0,
            'registrations_created': 0,
            'registrations_existing': 0,
        }

        legacy_program = None
        events_cache = {}
        users_cache = {}

        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter='\t')

            if self.debug:
                self.stdout.write(f"CSV headers: {csv_reader.fieldnames}")
                self.stdout.write('')

            for row in csv_reader:
                stats['total_rows'] += 1

                if stats['total_rows'] == 1 and self.dry_run:
                    legacy_program = self.ensure_program(stats)

                event = self.ensure_event(row, events_cache, stats)
                if not event:
                    stats['skipped_rows'] += 1
                    continue

                user = self.ensure_user(row, users_cache, stats)
                if not user:
                    stats['skipped_rows'] += 1
                    continue

                self.create_registration(row, event, user, stats)

        return stats

    def ensure_program(self, stats):
        program_name = 'Legacy Events'

        if not self.dry_run:
            program, created = Program.objects.get_or_create(name=program_name)
            if created:
                stats['programs_created'] += 1
            return program

        existing = Program.objects.filter(name=program_name).first()
        if not existing:
            stats['programs_created'] += 1
            if self.debug or stats['programs_created'] == 1:
                self.stdout.write(self.style.SUCCESS(
                    f'[DRY RUN] Would create Program: "{program_name}"'
                ))
            return None

        return existing

    def ensure_event(self, row, events_cache, stats):
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

        if not self.dry_run:
            event = Event.objects.filter(legacy_event_id=event_id).first()
            if event:
                stats['events_existing'] += 1
                events_cache[cache_key] = event
                return event

            program = self.ensure_program(stats)
            starts_at = timezone.make_aware(
                datetime.combine(event_date, datetime.min.time().replace(hour=9))
            )
            ends_at = timezone.make_aware(
                datetime.combine(event_date, datetime.min.time().replace(hour=12))
            )
            registration_closes_at = starts_at

            event = Event.objects.create(
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
            stats['events_created'] += 1
            events_cache[cache_key] = event

            if self.debug:
                self.stdout.write(self.style.SUCCESS(
                    f'Created event: {event_name} ({event_date})'
                ))

            return event

        existing = Event.objects.filter(legacy_event_id=event_id).first()
        if existing:
            stats['events_existing'] += 1
            events_cache[cache_key] = existing
            return existing

        stats['events_created'] += 1
        if self.debug or stats['events_created'] <= 5:
            self.stdout.write(self.style.SUCCESS(
                f'[DRY RUN] Would create event: {event_name} ({event_date}) [ID: {event_id}]'
            ))

        events_cache[cache_key] = f"dry_run_event_{event_id}"
        return events_cache[cache_key]

    def ensure_user(self, row, users_cache, stats):
        email = row.get('Email', '').strip().lower()
        first_name = row.get('First name', '').strip()
        last_name = row.get('Last name', '').strip()
        phone = row.get('Phone #', '').strip()

        if not email or not first_name or not last_name:
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with missing user data: {email}'
                ))
            return None

        if email in users_cache:
            return users_cache[email]

        if not self.dry_run:
            user = User.objects.filter(email=email).first()
            if user:
                stats['users_existing'] += 1
                users_cache[email] = user
                return user

            username = email
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{email}_{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,
            )
            user.set_unusable_password()
            user.save()

            UserProfile.objects.create(
                user=user,
                phone=phone,
                legacy=True,
            )

            stats['users_created'] += 1
            users_cache[email] = user

            if self.debug:
                self.stdout.write(self.style.SUCCESS(
                    f'Created user: {first_name} {last_name} ({email})'
                ))

            return user

        existing = User.objects.filter(email=email).first()
        if existing:
            stats['users_existing'] += 1
            users_cache[email] = existing
            return existing

        stats['users_created'] += 1
        if self.debug or stats['users_created'] <= 5:
            self.stdout.write(self.style.SUCCESS(
                f'[DRY RUN] Would create user: {first_name} {last_name} ({email})'
            ))

        users_cache[email] = f"dry_run_user_{email}"
        return users_cache[email]

    def create_registration(self, row, event, user, stats):
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

        if not self.dry_run:
            existing_registration = Registration.objects.filter(
                legacy_registration_id=legacy_reg_id
            ).first()
            if existing_registration:
                stats['registrations_existing'] += 1
                if self.debug:
                    self.stdout.write(
                        f'Registration already exists: {name} -> {event.name}'
                    )
                return
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
                state=Registration.STATE_CONFIRMED,
                submitted_at=submitted_at,
                confirmed_at=submitted_at,
                legacy=True,
                legacy_registration_id=legacy_reg_id,
            )
            registration.save()

            stats['registrations_created'] += 1

            if self.debug:
                self.stdout.write(
                    f'Created registration: {name} -> {event.name}'
                )
        else:
            stats['registrations_created'] += 1
            if self.debug or stats['registrations_created'] <= 5:
                event_name = event.name if hasattr(event, 'name') else str(event)
                self.stdout.write(
                    f'[DRY RUN] Would create registration: {name} -> {event_name}'
                )

    def generate_legacy_registration_id(self, event_id, email, submitted_at):
        composite_key = f"{event_id}_{email}_{submitted_at.isoformat()}"
        return hashlib.sha256(composite_key.encode()).hexdigest()

    def print_summary(self, stats):
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Import Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write(f'Total rows processed: {stats["total_rows"]}')
        self.stdout.write(f'Rows skipped (missing data): {stats["skipped_rows"]}')
        self.stdout.write('')

        if stats['programs_created'] > 0:
            label = '[DRY RUN] Would create' if self.dry_run else 'Created'
            self.stdout.write(f'{label} programs: {stats["programs_created"]}')
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would create events: {stats["events_created"]}')
            self.stdout.write(f'Events already exist: {stats["events_existing"]}')
            self.stdout.write('')
            self.stdout.write(f'[DRY RUN] Would create users: {stats["users_created"]}')
            self.stdout.write(f'Users already exist: {stats["users_existing"]}')
            self.stdout.write('')
            self.stdout.write(f'[DRY RUN] Would create registrations: {stats["registrations_created"]}')
            self.stdout.write(f'Registrations already exist: {stats["registrations_existing"]}')
        else:
            self.stdout.write(f'Events created: {stats["events_created"]}')
            self.stdout.write(f'Events already exist: {stats["events_existing"]}')
            self.stdout.write('')
            self.stdout.write(f'Users created: {stats["users_created"]}')
            self.stdout.write(f'Users already exist: {stats["users_existing"]}')
            self.stdout.write('')
            self.stdout.write(f'Registrations created: {stats["registrations_created"]}')
            self.stdout.write(f'Registrations already exist: {stats["registrations_existing"]}')

        self.stdout.write('')
        if self.dry_run:
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
