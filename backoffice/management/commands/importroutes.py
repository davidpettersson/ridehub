import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
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
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print additional debug information',
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        dry_run = options['dry_run']
        self.debug = options['debug']

        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file_path}'))
            return

        stats, routes_to_create, routes_to_update = self.process_csv(csv_file_path, dry_run)
        
        if not dry_run:
            self.save_changes(routes_to_create, routes_to_update)
            
        self.print_summary(stats, dry_run)

    def process_csv(self, csv_file_path, dry_run):
        stats = {
            'imported': 0,
            'updated': 0,
            'skipped_archived': 0,
            'skipped_existing': 0
        }
        
        now = timezone.now()
        routes_to_create = []
        routes_to_update = []
        
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            
            # Debug: Print CSV column headers
            if self.debug:
                self.stdout.write(f"CSV headers: {csv_reader.fieldnames}")
                
            for row in csv_reader:
                self.process_row(row, now, stats, routes_to_create, routes_to_update, dry_run)
                
        return stats, routes_to_create, routes_to_update
    
    def process_row(self, row, now, stats, routes_to_create, routes_to_update, dry_run):
        # Skip archived routes
        if row.get('Is Archived', '').lower() == 'yes':
            stats['skipped_archived'] += 1
            return

        route_name = row.get('Route name', '')
        route_url = row.get('Route URL', '')
        
        # Skip if we don't have the essential data
        if not route_name or not route_url:
            self.stdout.write(self.style.WARNING(f'Skipped row with missing name or URL'))
            return
            
        # Extract and convert distance and elevation gain if available
        distance = self._extract_integer_value(row.get('Distance', ''))
        # The column name in the CSV is "Elevation gain" (lowercase g)
        elevation_gain = self._extract_integer_value(row.get('Elevation gain', ''))
        
        if self.debug:
            self.stdout.write(f"Processing route: {route_name}")
            self.stdout.write(f"  - Distance: {distance} (from CSV: {row.get('Distance', 'N/A')})")
            self.stdout.write(f"  - Elevation gain: {elevation_gain} (from CSV: {row.get('Elevation gain', 'N/A')})")

        # Check if route with this URL already exists
        existing_route = Route.objects.filter(url=route_url).first()
        if existing_route:
            self.handle_existing_route(
                existing_route, route_name, route_url, distance, elevation_gain, 
                now, stats, routes_to_update, dry_run
            )
            return

        # Create new route
        self.handle_new_route(
            route_name, route_url, distance, elevation_gain, 
            now, stats, routes_to_create, dry_run
        )
    
    def handle_existing_route(self, existing_route, route_name, route_url, distance, 
                              elevation_gain, now, stats, routes_to_update, dry_run):
        stats['skipped_existing'] += 1
        
        if dry_run and self.debug:
            self.stdout.write(f"Existing route found: {route_name}")
            self.stdout.write(f"  - Current elevation_gain: {existing_route.elevation_gain}")
            self.stdout.write(f"  - CSV elevation_gain: {elevation_gain}")
            self.stdout.write(f"  - Should update: {elevation_gain is not None and existing_route.elevation_gain != elevation_gain}")
            
        if dry_run and not self.debug:
            return
            
        updated_fields = []
        
        if existing_route.name != route_name:
            existing_route.name = route_name
            updated_fields.append('name')
            
        if distance is not None and existing_route.distance != distance:
            if self.debug:
                self.stdout.write(f"  - Distance update needed: {existing_route.distance} → {distance}")
            existing_route.distance = distance
            updated_fields.append('distance')
            
        if elevation_gain is not None and existing_route.elevation_gain != elevation_gain:
            if self.debug:
                self.stdout.write(f"  - Elevation gain update needed: {existing_route.elevation_gain} → {elevation_gain}")
            existing_route.elevation_gain = elevation_gain
            updated_fields.append('elevation_gain')
            
        if updated_fields:
            existing_route.last_imported_at = now
            updated_fields.append('last_imported_at')
            routes_to_update.append((existing_route, updated_fields))
            stats['updated'] += 1
            
            field_list = ', '.join(updated_fields)
            self.stdout.write(
                self.style.WARNING(f'Will update route: {route_url} → {field_list}'))
        else:
            self.stdout.write(self.style.WARNING(f'No changes for route: {route_url}'))
    
    def handle_new_route(self, route_name, route_url, distance, elevation_gain, 
                         now, stats, routes_to_create, dry_run):
        stats['imported'] += 1
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'Would import: {route_url} → {route_name} (distance: {distance}, elevation: {elevation_gain})'))
            return
            
        route = Route(
            name=route_name, 
            url=route_url, 
            last_imported_at=now
        )
        if distance is not None:
            route.distance = distance
        if elevation_gain is not None:
            route.elevation_gain = elevation_gain
            
        routes_to_create.append(route)
    
    def save_changes(self, routes_to_create, routes_to_update):
        with transaction.atomic():
            # Bulk create all new routes
            if routes_to_create:
                Route.objects.bulk_create(routes_to_create)
            
            # Update existing routes one by one
            for route, updated_fields in routes_to_update:
                route.save(update_fields=updated_fields)
    
    def print_summary(self, stats, dry_run):
        self.stdout.write(self.style.SUCCESS(f'Import complete! Results:'))
        self.stdout.write(f'  - Routes imported: {stats["imported"]}')
        self.stdout.write(f'  - Routes updated: {stats["updated"]}')
        self.stdout.write(f'  - Archived routes skipped: {stats["skipped_archived"]}')
        self.stdout.write(f'  - Unchanged existing routes: {stats["skipped_existing"] - stats["updated"]}')

        if dry_run:
            self.stdout.write(self.style.NOTICE('This was a dry run. No changes were made to the database.'))
    
    def _extract_integer_value(self, value_str):
        """Convert string values to integers, handling float values."""
        if not value_str or value_str.strip() == '':
            return None
            
        try:
            # Try to convert to float first, then to int
            return int(float(value_str))
        except (ValueError, TypeError):
            return None