from django.core.management.base import BaseCommand
from django.db import transaction

import pandas as pd
import recordlinkage

from membership.models import Member, Registration
from membership.services.matching_service import UnionFind


class Command(BaseCommand):
    help = 'Find and merge duplicate Member records'

    FIELD_WEIGHTS = {
        'first_name': 3,
        'date_of_birth': 3,
        'sex': 3,
        'last_name': 2,
        'email': 1,
        'phone': 1,
        'city': 1,
        'country': 1,
        'postal_code': 1,
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

        self.stdout.write('Finding duplicate members')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Minimum confidence threshold: {self.min_confidence}')
        self.stdout.write('')

        members = list(Member.objects.all())
        self.stdout.write(f'Scanning {len(members)} members')

        if len(members) < 2:
            self.stdout.write('Not enough members to find duplicates.')
            return

        duplicate_clusters = self.find_duplicate_clusters(members)

        clusters_with_dupes = [c for c in duplicate_clusters if len(c) > 1]
        self.stdout.write(f'Found {len(clusters_with_dupes)} duplicate clusters')
        self.stdout.write('')

        if not clusters_with_dupes:
            self.stdout.write(self.style.SUCCESS('No duplicates found.'))
            return

        member_lookup = {m.id: m for m in members}

        stats = {'members_deleted': 0, 'registrations_unlinked': 0}

        if not self.dry_run:
            with transaction.atomic():
                self.merge_clusters(clusters_with_dupes, member_lookup, stats)
        else:
            self.merge_clusters(clusters_with_dupes, member_lookup, stats)

        self.print_summary(stats)

    def build_member_dataframe(self, members):
        data = []
        for member in members:
            data.append({
                'id': member.id,
                'first_name': (member.first_name or '').lower().strip(),
                'last_name': (member.last_name or '').lower().strip(),
                'date_of_birth': member.date_of_birth,
                'sex': (member.sex or '').lower().strip(),
                'email': (member.email or '').lower().strip(),
                'phone': ''.join(c for c in (member.phone or '') if c.isdigit()),
                'city': (member.city or '').lower().strip(),
                'country': (member.country or '').lower().strip(),
                'postal_code': (member.postal_code or '').lower().strip(),
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index('id')
        return df

    def find_duplicate_clusters(self, members):
        member_df = self.build_member_dataframe(members)

        if member_df.empty:
            return []

        indexer = recordlinkage.Index()
        indexer.add(recordlinkage.index.Block('date_of_birth'))
        indexer.add(recordlinkage.index.SortedNeighbourhood('last_name', window=3))
        pairs = indexer.index(member_df)

        if self.debug:
            self.stdout.write(f'Created {len(pairs)} candidate pairs')

        if len(pairs) == 0:
            return [[mid] for mid in member_df.index]

        compare = recordlinkage.Compare()
        compare.string('first_name', 'first_name', method='jarowinkler',
                       threshold=0.85, label='first_name')
        compare.string('last_name', 'last_name', method='jarowinkler',
                       threshold=0.85, label='last_name')
        compare.exact('date_of_birth', 'date_of_birth', label='date_of_birth')
        compare.exact('sex', 'sex', label='sex')
        compare.string('email', 'email', method='levenshtein',
                       threshold=0.9, label='email')
        compare.string('phone', 'phone', method='levenshtein',
                       threshold=0.8, label='phone')
        compare.string('city', 'city', method='jarowinkler',
                       threshold=0.85, label='city')
        compare.exact('country', 'country', label='country')
        compare.string('postal_code', 'postal_code', method='levenshtein',
                       threshold=0.9, label='postal_code')

        comparison_vectors = compare.compute(pairs, member_df, member_df)

        weighted = comparison_vectors.copy()
        for col in weighted.columns:
            if col in self.FIELD_WEIGHTS:
                weighted[col] = weighted[col] * self.FIELD_WEIGHTS[col]

        total_weight = sum(self.FIELD_WEIGHTS.get(col, 1)
                           for col in comparison_vectors.columns)
        confidence_scores = weighted.sum(axis=1) / total_weight

        matching_pairs = confidence_scores[confidence_scores >= self.min_confidence]

        if self.debug:
            self.stdout.write(f'Found {len(matching_pairs)} matching pairs')

        uf = UnionFind(member_df.index.tolist())
        for (id1, id2), score in matching_pairs.items():
            uf.union(id1, id2)

        return uf.get_clusters()

    def merge_clusters(self, clusters, member_lookup, stats):
        for cluster_ids in clusters:
            if len(cluster_ids) <= 1:
                continue

            members = [member_lookup[mid] for mid in cluster_ids]
            members.sort(key=lambda m: (m.cohort, m.id))

            keeper = members[0]
            to_delete = members[1:]

            self.stdout.write(f'DUPLICATE CLUSTER:')
            self.stdout.write(f'  Keeping: Member #{keeper.id}: {keeper.first_name} '
                              f'{keeper.last_name}, DOB {keeper.date_of_birth}, '
                              f'cohort {keeper.cohort}, {keeper.email}')

            for member in to_delete:
                reg_count = Registration.objects.filter(matched_member=member).count()
                self.stdout.write(f'  Deleting: Member #{member.id}: {member.first_name} '
                                  f'{member.last_name}, DOB {member.date_of_birth}, '
                                  f'cohort {member.cohort}, {member.email} '
                                  f'({reg_count} registrations)')

                if not self.dry_run:
                    Registration.objects.filter(matched_member=member).update(matched_member=None)
                    member.delete()

                stats['registrations_unlinked'] += reg_count
                stats['members_deleted'] += 1

            self.stdout.write('')

    def print_summary(self, stats):
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Merge Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(f'[DRY RUN] Would delete members: {stats["members_deleted"]}')
            self.stdout.write(f'[DRY RUN] Would unlink registrations: {stats["registrations_unlinked"]}')
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                'This was a dry run. No changes were made to the database.'
            ))
        else:
            self.stdout.write(f'Members deleted: {stats["members_deleted"]}')
            self.stdout.write(f'Registrations unlinked: {stats["registrations_unlinked"]}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Merge completed successfully!'))
            self.stdout.write('')
            self.stdout.write('Run "python manage.py matchregistrations" to re-match '
                              'orphaned registrations.')
