import sys

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backoffice.services.route_service import (
    ACTION_OVERWRITE,
    ACTION_SKIP,
    ACTION_DELETE,
    CONFLICT_DELETE,
    CONFLICT_UPDATE,
    RouteImportService,
)


CSV_URL_TEMPLATE = 'https://ridewithgps.com/organizations/{slug}/routes.csv'
HTTP_TIMEOUT_SECONDS = 30


class Command(BaseCommand):
    help = 'Sync routes from Ride with GPS public CSV feed.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--debug', action='store_true')
        parser.add_argument('--non-interactive', action='store_true',
                            help='Skip routes with manual-edit conflicts instead of prompting.')
        parser.add_argument('--url', type=str, default=None,
                            help='Override the CSV URL (defaults to RWGPS_ORG_SLUG).')

    def handle(self, *args, **options):
        url = options['url'] or CSV_URL_TEMPLATE.format(slug=settings.RWGPS_ORG_SLUG)
        dry_run = options['dry_run']
        non_interactive = options['non_interactive']

        self.stdout.write(f'Fetching {url}')
        try:
            response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f'Failed to fetch CSV: {exc}')

        text = response.content.decode('utf-8-sig')

        bulk_decision = {'value': None}

        def on_conflict(route, csv_row, conflict_type):
            if non_interactive:
                return ACTION_SKIP
            if bulk_decision['value'] is not None:
                return bulk_decision['value']
            return self._prompt(route, csv_row, conflict_type, bulk_decision)

        service = RouteImportService()
        stats = service.import_from_csv_text(text, on_conflict=on_conflict, dry_run=dry_run)

        self._print_summary(stats, dry_run)

    def _prompt(self, route, csv_row, conflict_type, bulk_decision):
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            f'Conflict: route "{route.name}" ({route.url}) was manually edited '
            f'(updated_at={route.updated_at.isoformat()}, '
            f'last_imported_at={route.last_imported_at.isoformat() if route.last_imported_at else "never"}).'
        ))

        if conflict_type == CONFLICT_UPDATE and csv_row is not None:
            self.stdout.write(
                f'  DB:  name={route.name!r}, distance={route.distance}, elevation={route.elevation_gain}, archived={route.archived}'
            )
            self.stdout.write(
                f'  CSV: name={csv_row.name!r}, distance={csv_row.distance}, elevation={csv_row.elevation_gain}, archived={csv_row.archived}'
            )
            choices = '[o]verwrite / [s]kip / [O]all-overwrite / [S]all-skip'
            mapping = {'o': ACTION_OVERWRITE, 's': ACTION_SKIP}
            bulk = {'O': ACTION_OVERWRITE, 'S': ACTION_SKIP}
        else:
            self.stdout.write('  Route missing from RWGPS feed; would be marked deleted.')
            choices = '[d]elete / [s]kip / [D]all-delete / [S]all-skip'
            mapping = {'d': ACTION_DELETE, 's': ACTION_SKIP}
            bulk = {'D': ACTION_DELETE, 'S': ACTION_SKIP}

        while True:
            self.stdout.write(f'  Choose {choices}: ', ending='')
            self.stdout.flush()
            answer = sys.stdin.readline().strip()
            if answer in bulk:
                bulk_decision['value'] = bulk[answer]
                return bulk[answer]
            if answer in mapping:
                return mapping[answer]
            self.stdout.write(self.style.ERROR('  Invalid choice.'))

    def _print_summary(self, stats, dry_run):
        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry run - no changes were saved.'))
        self.stdout.write(self.style.SUCCESS('Sync complete:'))
        self.stdout.write(f'  Imported:           {stats.imported}')
        self.stdout.write(f'  Updated:            {stats.updated}')
        self.stdout.write(f'  Archived (delta):   {stats.archived}')
        self.stdout.write(f'  Unarchived:         {stats.unarchived}')
        self.stdout.write(f'  Deleted:            {stats.deleted}')
        self.stdout.write(f'  Undeleted:          {stats.undeleted}')
        self.stdout.write(f'  Unchanged:          {stats.unchanged}')
        self.stdout.write(f'  Conflicts resolved: {stats.conflicts_resolved}')
        self.stdout.write(f'  Conflicts skipped:  {stats.conflicts_skipped}')
        for warning in stats.warnings:
            self.stdout.write(self.style.WARNING(f'  ! {warning}'))
