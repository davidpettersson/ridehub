import os

from django.core.management.base import BaseCommand

from backoffice.services.route_service import ACTION_SKIP, RouteImportService


class Command(BaseCommand):
    help = 'Import routes from a local CSV file exported from Ride with GPS.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--debug', action='store_true')

    def handle(self, *args, **options):
        path = options['csv_file']
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR(f'File not found: {path}'))
            return

        with open(path, 'r', encoding='utf-8-sig') as fh:
            text = fh.read()

        service = RouteImportService()
        stats = service.import_from_csv_text(
            text,
            on_conflict=lambda *_: ACTION_SKIP,
            dry_run=options['dry_run'],
        )

        self._print_summary(stats, options['dry_run'])

    def _print_summary(self, stats, dry_run):
        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry run - no changes were saved.'))
        self.stdout.write(self.style.SUCCESS('Import complete:'))
        self.stdout.write(f'  Imported:           {stats.imported}')
        self.stdout.write(f'  Updated:            {stats.updated}')
        self.stdout.write(f'  Archived (delta):   {stats.archived}')
        self.stdout.write(f'  Unarchived:         {stats.unarchived}')
        self.stdout.write(f'  Deleted:            {stats.deleted}')
        self.stdout.write(f'  Undeleted:          {stats.undeleted}')
        self.stdout.write(f'  Unchanged:          {stats.unchanged}')
        self.stdout.write(f'  Conflicts skipped:  {stats.conflicts_skipped}')
