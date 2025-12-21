from django.core.management.base import BaseCommand
from django.db import transaction

from membership.services.matching_service import MatchingService


class Command(BaseCommand):
    help = 'Match Registration records to Member records using recordlinkage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.7,
            help='Minimum confidence threshold for matching (default: 0.7)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save to database, just print what would be done',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print additional debug information',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.debug = options['debug']
        min_confidence = options['min_confidence']

        self.stdout.write('Starting registration matching')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Minimum confidence threshold: {min_confidence}')
        self.stdout.write('')

        service = MatchingService(
            min_confidence=min_confidence,
            debug=self.debug,
            stdout=self.stdout,
            style=self.style,
        )

        if not self.dry_run:
            with transaction.atomic():
                result = service.run_matching(dry_run=False)
        else:
            result = service.run_matching(dry_run=True)

        self.print_summary(result)

    def print_summary(self, result):
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Matching Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        self.stdout.write(f'Unique person clusters found: {result.clusters_found}')
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would create new members: '
                              f'{result.new_members_created}')
            self.stdout.write(f'[DRY RUN] Would update existing members: '
                              f'{result.members_updated}')
            self.stdout.write(f'[DRY RUN] Would link registrations: '
                              f'{result.registrations_linked}')
        else:
            self.stdout.write(f'New members created: {result.new_members_created}')
            self.stdout.write(f'Existing members updated: {result.members_updated}')
            self.stdout.write(f'Registrations linked: {result.registrations_linked}')

        self.stdout.write(f'Ambiguous clusters (skipped): {result.ambiguous_skipped}')
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Matching completed successfully!'))
