import csv
import os
import zoneinfo
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from membership.models import Registration


class Command(BaseCommand):
    help = 'Import registration records from a CCN Bikes CSV file'

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

        self.stdout.write(f'Processing CSV file: {csv_file_path}')
        self.stdout.write('=' * 60)
        self.stdout.write('')

        self.stats = {'total': 0, 'created': 0, 'updated': 0, 'skipped': 0}
        self.operations = []

        self.process_csv(csv_file_path)

        if not self.dry_run:
            self.save_operations()

        self.print_summary()

    def process_csv(self, csv_file_path):
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)

            if self.debug:
                self.stdout.write(f'CSV headers: {csv_reader.fieldnames}')
                self.stdout.write('')

            for row in csv_reader:
                self.stats['total'] += 1
                self.process_row(row)

    def process_row(self, row):
        identity_str = row.get('Identity ID', '').strip()
        first_name = row.get('First Name', '').strip()
        last_name = row.get('Last Name', '').strip()

        if not identity_str or not first_name or not last_name:
            self.stats['skipped'] += 1
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with missing required data: identity={identity_str}, '
                    f'name={first_name} {last_name}'
                ))
            return

        try:
            identity = int(identity_str)
        except ValueError:
            self.stats['skipped'] += 1
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with invalid identity: {identity_str}'
                ))
            return

        registered_at = self.parse_datetime(row.get('Reg Checkout Date', '').strip())
        if not registered_at:
            self.stats['skipped'] += 1
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with invalid date: {row.get("Reg Checkout Date", "")}'
                ))
            return

        date_of_birth = self.parse_date(row.get('DOB', '').strip())
        if not date_of_birth:
            self.stats['skipped'] += 1
            if self.debug:
                self.stdout.write(self.style.WARNING(
                    f'Skipping row with invalid DOB: {row.get("DOB", "")}'
                ))
            return

        sex = row.get('Sex', '').strip()
        category = row.get('Category', '').strip()
        city = row.get('Registrant City', '').strip()
        country = row.get('Registrant Country', '').strip()
        postal_code = row.get('Registrant Postal Code', '').strip()
        email = row.get('Email', '').strip().lower()
        phone = row.get('Registrant Telephone', '').strip()
        duration = row.get('How long have you been a member of the OBC?', '').strip()

        existing = Registration.objects.filter(
            identity=identity, registered_at=registered_at
        ).first()

        if existing:
            existing.first_name = first_name
            existing.last_name = last_name
            existing.sex = sex
            existing.date_of_birth = date_of_birth
            existing.category = category
            existing.city = city
            existing.country = country
            existing.postal_code = postal_code
            existing.email = email
            existing.phone = phone
            existing.duration = duration
            self.operations.append(existing)
            self.stats['updated'] += 1

            if self.debug:
                label = '[DRY RUN] Would update' if self.dry_run else 'Updating'
                self.stdout.write(f'{label}: {first_name} {last_name} (ID: {identity})')
        else:
            registration = Registration(
                identity=identity,
                registered_at=registered_at,
                first_name=first_name,
                last_name=last_name,
                sex=sex,
                date_of_birth=date_of_birth,
                category=category,
                city=city,
                country=country,
                postal_code=postal_code,
                email=email,
                phone=phone,
                duration=duration,
            )
            self.operations.append(registration)
            self.stats['created'] += 1

            if self.debug:
                label = '[DRY RUN] Would create' if self.dry_run else 'Creating'
                self.stdout.write(self.style.SUCCESS(
                    f'{label}: {first_name} {last_name} (ID: {identity})'
                ))

    def parse_datetime(self, date_str):
        if not date_str:
            return None
        tz = zoneinfo.ZoneInfo('America/Toronto')
        try:
            dt = datetime.strptime(date_str, '%m/%d/%Y %H:%M')
            return dt.replace(tzinfo=tz)
        except ValueError:
            pass
        try:
            dt = datetime.strptime(date_str, '%m/%d/%Y')
            return dt.replace(tzinfo=tz)
        except ValueError:
            return None

    def parse_date(self, date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%m/%d/%Y').date()
        except ValueError:
            return None

    def save_operations(self):
        with transaction.atomic():
            for registration in self.operations:
                registration.save()

    def print_summary(self):
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Import Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write(f'Total rows processed: {self.stats["total"]}')
        self.stdout.write(f'Rows skipped: {self.stats["skipped"]}')
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would create: {self.stats["created"]}')
            self.stdout.write(f'[DRY RUN] Would update: {self.stats["updated"]}')
        else:
            self.stdout.write(f'Created: {self.stats["created"]}')
            self.stdout.write(f'Updated: {self.stats["updated"]}')

        self.stdout.write('')
        if self.dry_run:
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
