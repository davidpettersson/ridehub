from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Exists, OuterRef
from backoffice.models import Event, Registration, UserProfile


class Command(BaseCommand):
    help = 'Remove all legacy data imported from WebScorer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not delete from database, just print what would be removed',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print additional debug information',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.debug = options['debug']

        self.stdout.write('Analyzing legacy data for removal...')
        self.stdout.write('=' * 60)
        self.stdout.write('')

        stats = self.analyze_data()
        self.print_analysis(stats)

        if not self.dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Proceeding with deletion...'))
            self.stdout.write('')
            self.remove_data(stats)

        self.print_summary(stats)

    def analyze_data(self):
        stats = {
            'registrations_to_delete': 0,
            'events_to_delete': 0,
            'users_with_only_legacy': 0,
            'users_with_mixed_data': 0,
            'profiles_to_delete': 0,
        }

        stats['registrations_to_delete'] = Registration.objects.filter(legacy=True).count()
        stats['events_to_delete'] = Event.objects.filter(legacy=True).count()

        legacy_users = User.objects.filter(profile__legacy=True)

        has_non_legacy_registration = Registration.objects.filter(
            user=OuterRef('pk'),
            legacy=False
        )

        users_with_only_legacy = legacy_users.annotate(
            has_non_legacy=Exists(has_non_legacy_registration)
        ).filter(has_non_legacy=False)

        users_with_mixed = legacy_users.annotate(
            has_non_legacy=Exists(has_non_legacy_registration)
        ).filter(has_non_legacy=True)

        stats['users_with_only_legacy'] = users_with_only_legacy.count()
        stats['users_with_mixed_data'] = users_with_mixed.count()
        stats['profiles_to_delete'] = stats['users_with_only_legacy']

        if self.debug:
            self.stdout.write(self.style.NOTICE('Debug: Sample users with only legacy data:'))
            for user in users_with_only_legacy[:5]:
                self.stdout.write(f'  - {user.get_full_name()} ({user.email})')
            self.stdout.write('')

            if stats['users_with_mixed_data'] > 0:
                self.stdout.write(self.style.NOTICE('Debug: Sample users with mixed data (will be preserved):'))
                for user in users_with_mixed[:5]:
                    self.stdout.write(f'  - {user.get_full_name()} ({user.email})')
                self.stdout.write('')

        return stats

    def remove_data(self, stats):
        with transaction.atomic():
            legacy_registrations = Registration.objects.filter(legacy=True)
            deleted_registrations = legacy_registrations.delete()
            self.stdout.write(f'Deleted {deleted_registrations[0]} registrations')

            legacy_events = Event.objects.filter(legacy=True)
            deleted_events = legacy_events.delete()
            self.stdout.write(f'Deleted {deleted_events[0]} events')

            has_non_legacy_registration = Registration.objects.filter(
                user=OuterRef('pk'),
                legacy=False
            )

            users_to_delete = User.objects.filter(
                profile__legacy=True
            ).annotate(
                has_non_legacy=Exists(has_non_legacy_registration)
            ).filter(has_non_legacy=False)

            user_count = users_to_delete.count()
            deleted_users = users_to_delete.delete()
            self.stdout.write(f'Deleted {user_count} users (and their profiles)')

    def print_analysis(self, stats):
        self.stdout.write(self.style.WARNING('Data to be removed:'))
        self.stdout.write('')
        self.stdout.write(f'  Registrations: {stats["registrations_to_delete"]:,}')
        self.stdout.write(f'  Events: {stats["events_to_delete"]:,}')
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('User Analysis:'))
        self.stdout.write(f'  Users with ONLY legacy data: {stats["users_with_only_legacy"]:,} (will be deleted)')
        self.stdout.write(f'  Users with legacy + non-legacy registrations: {stats["users_with_mixed_data"]:,} (will be PRESERVED)')
        self.stdout.write(f'  UserProfiles to delete: {stats["profiles_to_delete"]:,}')
        self.stdout.write('')

    def print_summary(self, stats):
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would delete {stats["registrations_to_delete"]:,} legacy registrations')
            self.stdout.write(f'[DRY RUN] Would delete {stats["events_to_delete"]:,} legacy events')
            self.stdout.write(f'[DRY RUN] Would delete {stats["users_with_only_legacy"]:,} users with only legacy data')
            self.stdout.write(f'[DRY RUN] Would preserve {stats["users_with_mixed_data"]:,} users with non-legacy registrations')
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(f'Deleted {stats["registrations_to_delete"]:,} legacy registrations')
            self.stdout.write(f'Deleted {stats["events_to_delete"]:,} legacy events')
            self.stdout.write(f'Deleted {stats["users_with_only_legacy"]:,} users with only legacy data')
            self.stdout.write(f'Preserved {stats["users_with_mixed_data"]:,} users with non-legacy registrations')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Legacy data removal completed successfully!'))
