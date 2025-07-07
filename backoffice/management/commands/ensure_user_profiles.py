from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from backoffice.models import UserProfile


class Command(BaseCommand):
    help = 'Ensure all existing users have profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually creating profiles',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find users without profiles
        users_without_profiles = []
        for user in User.objects.all():
            try:
                # Try to access the profile
                user.profile
            except UserProfile.DoesNotExist:
                users_without_profiles.append(user)
        
        if not users_without_profiles:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles!')
            )
            return
        
        self.stdout.write(
            f'Found {len(users_without_profiles)} users without profiles:'
        )
        
        for user in users_without_profiles:
            identifier = user.email if user.email else user.username
            self.stdout.write(f'  - {identifier} (ID: {user.id})')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No profiles were created. Use without --dry-run to create profiles.')
            )
            return
        
        # Create profiles for users that don't have them
        created_count = 0
        for user in users_without_profiles:
            profile = UserProfile.objects.create(user=user)
            created_count += 1
            identifier = user.email if user.email else user.username
            self.stdout.write(f'Created profile for {identifier}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} user profiles!')
        ) 