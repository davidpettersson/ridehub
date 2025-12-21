from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

import pandas as pd
import recordlinkage

from membership.models import Member


class Command(BaseCommand):
    help = 'Match Member records to User records'

    FIELD_WEIGHTS = {
        'first_name': 3,
        'last_name': 3,
        'email': 1,
        'phone': 1,
    }

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
            help='Do not make changes, just print what would be done',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print additional debug information',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.debug = options['debug']
        self.min_confidence = options['min_confidence']

        self.stdout.write('Matching members to users')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Minimum confidence threshold: {self.min_confidence}')
        self.stdout.write('')

        members = list(Member.objects.filter(matched_user__isnull=True))
        self.stdout.write(f'Found {len(members)} unlinked members')

        users = list(User.objects.select_related('profile').all())
        self.stdout.write(f'Found {len(users)} users')

        if len(members) == 0:
            self.stdout.write('No unlinked members to process.')
            return

        if len(users) == 0:
            self.stdout.write('No users to match against.')
            return

        matches = self.find_matches(members, users)

        self.stdout.write(f'Found {len(matches)} matches')
        self.stdout.write('')

        stats = {'linked': 0}

        if not self.dry_run:
            with transaction.atomic():
                self.apply_matches(matches, stats)
        else:
            self.apply_matches(matches, stats)

        self.print_summary(stats)

    def build_member_dataframe(self, members):
        data = []
        for member in members:
            data.append({
                'id': member.id,
                'first_name': (member.first_name or '').lower().strip(),
                'last_name': (member.last_name or '').lower().strip(),
                'email': (member.email or '').lower().strip(),
                'phone': ''.join(c for c in (member.phone or '') if c.isdigit()),
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index('id')
        return df

    def build_user_dataframe(self, users):
        data = []
        for user in users:
            phone = ''
            if hasattr(user, 'profile') and user.profile and user.profile.phone:
                phone = ''.join(c for c in str(user.profile.phone) if c.isdigit())

            data.append({
                'id': user.id,
                'first_name': (user.first_name or '').lower().strip(),
                'last_name': (user.last_name or '').lower().strip(),
                'email': (user.email or '').lower().strip(),
                'phone': phone,
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index('id')
        return df

    def find_matches(self, members, users):
        member_df = self.build_member_dataframe(members)
        user_df = self.build_user_dataframe(users)

        if member_df.empty or user_df.empty:
            return []

        indexer = recordlinkage.Index()
        indexer.add(recordlinkage.index.SortedNeighbourhood('last_name', window=5))
        indexer.add(recordlinkage.index.Block('email'))
        pairs = indexer.index(member_df, user_df)

        if self.debug:
            self.stdout.write(f'Created {len(pairs)} candidate pairs')

        if len(pairs) == 0:
            return []

        compare = recordlinkage.Compare()
        compare.string('first_name', 'first_name', method='jarowinkler',
                       threshold=0.85, label='first_name')
        compare.string('last_name', 'last_name', method='jarowinkler',
                       threshold=0.85, label='last_name')
        compare.string('email', 'email', method='levenshtein',
                       threshold=0.9, label='email')
        compare.string('phone', 'phone', method='levenshtein',
                       threshold=0.8, label='phone')

        comparison_vectors = compare.compute(pairs, member_df, user_df)

        weighted = comparison_vectors.copy()
        for col in weighted.columns:
            if col in self.FIELD_WEIGHTS:
                weighted[col] = weighted[col] * self.FIELD_WEIGHTS[col]

        total_weight = sum(self.FIELD_WEIGHTS.get(col, 1)
                           for col in comparison_vectors.columns)
        confidence_scores = weighted.sum(axis=1) / total_weight

        above_threshold = confidence_scores[confidence_scores >= self.min_confidence]

        if self.debug:
            self.stdout.write(f'Found {len(above_threshold)} pairs above threshold')

        member_lookup = {m.id: m for m in members}
        user_lookup = {u.id: u for u in users}

        member_best_match = {}
        for (member_id, user_id), score in above_threshold.items():
            if member_id not in member_best_match or score > member_best_match[member_id][1]:
                member_best_match[member_id] = (user_id, score)

        matches = []
        for member_id, (user_id, score) in member_best_match.items():
            matches.append({
                'member': member_lookup[member_id],
                'user': user_lookup[user_id],
                'confidence': score,
            })

        return matches

    def apply_matches(self, matches, stats):
        for match in matches:
            member = match['member']
            user = match['user']
            confidence = match['confidence']

            self.stdout.write(
                f'MATCH: Member #{member.id} ({member.first_name} {member.last_name}, '
                f'{member.email}) -> User #{user.id} ({user.first_name} {user.last_name}, '
                f'{user.email}) [confidence: {confidence:.2f}]'
            )

            if not self.dry_run:
                member.matched_user = user
                member.save(update_fields=['matched_user'])

            stats['linked'] += 1

    def print_summary(self, stats):
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Match Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would link members to users: {stats["linked"]}')
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(f'Members linked to users: {stats["linked"]}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Matching completed successfully!'))
