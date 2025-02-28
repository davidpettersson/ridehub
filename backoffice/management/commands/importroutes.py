import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from backoffice.models import Route


class Command(BaseCommand):
    help = 'Import routes from a CSV file from Ride With GPS'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not save to database, just print what would be imported',
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        dry_run = options['dry_run']

        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file_path}'))
            return

        imported = 0
        skipped_archived = 0
        skipped_existing = 0

        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)

            # Keep track of routes to create in bulk
            routes_to_create = []

            for row in csv_reader:
                # Skip archived routes
                if row['Is Archived'].lower() == 'yes':
                    skipped_archived += 1
                    continue

                route_name = row['Route name']
                route_url = row['Route URL']

                # Check if route with this URL already exists
                if Route.objects.filter(url=route_url).exists():
                    if not dry_run:
                        # Update the name if needed
                        route = Route.objects.get(url=route_url)
                        if route.name != route_name:
                            route.name = route_name
                            route.save()
                            self.stdout.write(
                                self.style.WARNING(f'Updated existing route name: {route_url} → {route_name}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'Skipped existing route: {route_url}'))
                    skipped_existing += 1
                    continue

                # Create new route
                if dry_run:
                    self.stdout.write(self.style.SUCCESS(f'Would import: {route_url} → {route_name}'))
                else:
                    routes_to_create.append(Route(name=route_name, url=route_url))

                imported += 1

            # Bulk create all routes at once for better performance
            if routes_to_create and not dry_run:
                with transaction.atomic():
                    Route.objects.bulk_create(routes_to_create)

        # Print summary
        self.stdout.write(self.style.SUCCESS(f'Import complete! Results:'))
        self.stdout.write(f'  - Routes imported: {imported}')
        self.stdout.write(f'  - Archived routes skipped: {skipped_archived}')
        self.stdout.write(f'  - Existing routes skipped/updated: {skipped_existing}')

        if dry_run:
            self.stdout.write(self.style.NOTICE('This was a dry run. No changes were made to the database.'))