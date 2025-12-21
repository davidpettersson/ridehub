from dataclasses import dataclass, field

import pandas as pd
import recordlinkage
from django.db.models import Max, QuerySet

from membership.models import Member, Registration


@dataclass
class MatchingResult:
    new_members_created: int = 0
    members_updated: int = 0
    registrations_linked: int = 0
    clusters_found: int = 0
    ambiguous_skipped: int = 0
    low_confidence_skipped: int = 0
    ambiguous_registrations: list = field(default_factory=list)
    low_confidence_registrations: list = field(default_factory=list)


class UnionFind:
    def __init__(self, elements):
        self.parent = {e: e for e in elements}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py

    def get_clusters(self):
        clusters = {}
        for element in self.parent:
            root = self.find(element)
            clusters.setdefault(root, []).append(element)
        return list(clusters.values())


class MatchingService:
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

    def __init__(self, min_confidence: float = 0.8, debug: bool = False,
                 stdout=None, style=None):
        self.min_confidence = min_confidence
        self.debug = debug
        self.stdout = stdout
        self.style = style

    def log(self, message, style_func=None):
        if self.stdout:
            if style_func:
                self.stdout.write(style_func(message))
            else:
                self.stdout.write(message)

    def log_debug(self, message):
        if self.debug:
            self.log(message)

    def fetch_unprocessed_registrations(self) -> QuerySet[Registration]:
        return Registration.objects.filter(matched_member__isnull=True)

    def build_registration_dataframe(self, registrations) -> pd.DataFrame:
        data = []
        for reg in registrations:
            data.append({
                'id': reg.id,
                'first_name': reg.first_name or '',
                'last_name': reg.last_name or '',
                'date_of_birth': reg.date_of_birth,
                'sex': reg.sex or '',
                'email': reg.email or '',
                'phone': reg.phone or '',
                'city': reg.city or '',
                'country': reg.country or '',
                'postal_code': reg.postal_code or '',
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index('id')
        return self.clean_dataframe(df)

    def build_member_dataframe(self, members: QuerySet) -> pd.DataFrame:
        data = []
        for member in members:
            data.append({
                'id': member.id,
                'first_name': member.first_name or '',
                'last_name': member.last_name or '',
                'date_of_birth': member.date_of_birth,
                'sex': member.sex or '',
                'email': member.email or '',
                'phone': member.phone or '',
                'city': member.city or '',
                'country': member.country or '',
                'postal_code': member.postal_code or '',
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index('id')
        return self.clean_dataframe(df)

    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()

        text_columns = ['first_name', 'last_name', 'email', 'city', 'country', 'postal_code']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower().str.strip()

        if 'phone' in df.columns:
            df['phone'] = df['phone'].astype(str).str.replace(r'[^\d]', '', regex=True)

        if 'sex' in df.columns:
            df['sex'] = df['sex'].astype(str).str.lower().str.strip()

        return df

    def create_dedup_candidate_pairs(self, reg_df: pd.DataFrame) -> pd.MultiIndex:
        indexer = recordlinkage.Index()
        indexer.add(recordlinkage.index.Block('date_of_birth'))
        indexer.add(recordlinkage.index.SortedNeighbourhood('last_name', window=3))
        return indexer.index(reg_df)

    def create_linkage_candidate_pairs(self, reg_df: pd.DataFrame,
                                       member_df: pd.DataFrame) -> pd.MultiIndex:
        indexer = recordlinkage.Index()
        indexer.add(recordlinkage.index.Block('date_of_birth'))
        indexer.add(recordlinkage.index.SortedNeighbourhood('last_name', window=3))
        return indexer.index(reg_df, member_df)

    def compare_pairs(self, pairs: pd.MultiIndex, df_a: pd.DataFrame,
                      df_b: pd.DataFrame = None) -> pd.DataFrame:
        if df_b is None:
            df_b = df_a

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

        return compare.compute(pairs, df_a, df_b)

    def apply_weights(self, comparison_vectors: pd.DataFrame) -> pd.DataFrame:
        weighted = comparison_vectors.copy()
        for col in weighted.columns:
            if col in self.FIELD_WEIGHTS:
                weighted[col] = weighted[col] * self.FIELD_WEIGHTS[col]
        return weighted

    def calculate_confidence(self, comparison_vectors: pd.DataFrame) -> pd.Series:
        weighted = self.apply_weights(comparison_vectors)
        total_weight = sum(self.FIELD_WEIGHTS.get(col, 1) for col in comparison_vectors.columns)
        scores = weighted.sum(axis=1) / total_weight
        return scores

    def deduplicate_registrations(self, registrations: list) -> list:
        if len(registrations) <= 1:
            return [[reg.id] for reg in registrations]

        reg_df = self.build_registration_dataframe(registrations)

        if reg_df.empty:
            return [[reg.id] for reg in registrations]

        pairs = self.create_dedup_candidate_pairs(reg_df)
        self.log_debug(f'Deduplication: created {len(pairs)} candidate pairs')

        if len(pairs) == 0:
            return [[reg_id] for reg_id in reg_df.index]

        comparison_vectors = self.compare_pairs(pairs, reg_df)
        confidence_scores = self.calculate_confidence(comparison_vectors)

        matching_pairs = confidence_scores[confidence_scores >= self.min_confidence]
        self.log_debug(f'Deduplication: found {len(matching_pairs)} matching pairs')

        uf = UnionFind(reg_df.index.tolist())
        for (id1, id2), score in matching_pairs.items():
            uf.union(id1, id2)

        clusters = uf.get_clusters()
        self.log_debug(f'Deduplication: formed {len(clusters)} clusters')

        return clusters

    def find_matching_member_for_cluster(self, cluster_reg_ids: list,
                                         reg_lookup: dict,
                                         members_list: list) -> tuple:
        if not members_list:
            return None, 0.0

        cluster_regs = [reg_lookup[rid] for rid in cluster_reg_ids]
        reg_df = self.build_registration_dataframe(cluster_regs)
        member_df = self.build_member_dataframe(members_list)

        if reg_df.empty or member_df.empty:
            return None, 0.0

        pairs = self.create_linkage_candidate_pairs(reg_df, member_df)

        if len(pairs) == 0:
            return None, 0.0

        comparison_vectors = self.compare_pairs(pairs, reg_df, member_df)
        confidence_scores = self.calculate_confidence(comparison_vectors)

        if confidence_scores.empty:
            return None, 0.0

        above_threshold = confidence_scores[confidence_scores >= self.min_confidence]

        if above_threshold.empty:
            return None, 0.0

        member_scores = {}
        for (reg_id, member_id), score in above_threshold.items():
            if member_id not in member_scores or score > member_scores[member_id]:
                member_scores[member_id] = score

        if not member_scores:
            return None, 0.0

        sorted_members = sorted(member_scores.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_members) >= 2:
            score_diff = sorted_members[0][1] - sorted_members[1][1]
            if score_diff <= 0.1:
                return 'ambiguous', sorted_members

        best_member_id, best_score = sorted_members[0]
        member_lookup = {m.id: m for m in members_list}
        return member_lookup[best_member_id], best_score

    def get_most_recent_registration(self, cluster_reg_ids: list,
                                     reg_lookup: dict) -> Registration:
        regs = [reg_lookup[rid] for rid in cluster_reg_ids]
        return max(regs, key=lambda r: r.registered_at)

    def get_earliest_registration(self, cluster_reg_ids: list,
                                  reg_lookup: dict) -> Registration:
        regs = [reg_lookup[rid] for rid in cluster_reg_ids]
        return min(regs, key=lambda r: r.registered_at)

    def create_member_from_registration(self, registration: Registration,
                                        cohort_registration: Registration) -> Member:
        cohort = cohort_registration.registered_at.date().replace(day=1)
        return Member.objects.create(
            first_name=registration.first_name,
            last_name=registration.last_name,
            date_of_birth=registration.date_of_birth,
            sex=registration.sex,
            category=registration.category,
            city=registration.city,
            country=registration.country,
            postal_code=registration.postal_code,
            email=registration.email,
            phone=registration.phone,
            cohort=cohort,
            last_registration_year=registration.year,
        )

    def update_member_from_registration(self, member: Member,
                                        registration: Registration) -> bool:
        latest_reg = (Registration.objects
                      .filter(matched_member=member)
                      .order_by('-registered_at')
                      .first())

        if latest_reg:
            if registration.registered_at <= latest_reg.registered_at:
                return False

        member.first_name = registration.first_name
        member.last_name = registration.last_name
        member.date_of_birth = registration.date_of_birth
        member.sex = registration.sex
        member.category = registration.category
        member.city = registration.city
        member.country = registration.country
        member.postal_code = registration.postal_code
        member.email = registration.email
        member.phone = registration.phone
        member.save()
        return True

    def update_cohort_if_earlier(self, member: Member,
                                 registration: Registration) -> None:
        reg_cohort = registration.registered_at.date().replace(day=1)
        if reg_cohort < member.cohort:
            member.cohort = reg_cohort
            member.save(update_fields=['cohort'])

    def update_last_registration_years(self) -> int:
        members_updated = 0

        for member in Member.objects.all():
            latest_year = (Registration.objects
                           .filter(matched_member=member)
                           .aggregate(max_year=Max('year'))['max_year'])

            if latest_year and latest_year != member.last_registration_year:
                member.last_registration_year = latest_year
                member.save(update_fields=['last_registration_year'])
                members_updated += 1

        return members_updated

    def run_matching(self, dry_run: bool = False) -> MatchingResult:
        result = MatchingResult()

        unprocessed = self.fetch_unprocessed_registrations()
        unprocessed_list = list(unprocessed)

        if not unprocessed_list:
            self.log('No unprocessed registrations found.')
            return result

        self.log(f'Found {len(unprocessed_list)} unprocessed registrations')

        members = Member.objects.all()
        members_list = list(members)

        self.log(f'Found {len(members_list)} existing members')

        self.log('Phase 1: Deduplicating registrations...')
        clusters = self.deduplicate_registrations(unprocessed_list)
        result.clusters_found = len(clusters)
        self.log(f'Found {len(clusters)} unique person clusters')

        reg_lookup = {r.id: r for r in unprocessed_list}

        self.log('Phase 2: Matching clusters to members...')
        for cluster_reg_ids in clusters:
            most_recent_reg = self.get_most_recent_registration(cluster_reg_ids, reg_lookup)
            earliest_reg = self.get_earliest_registration(cluster_reg_ids, reg_lookup)

            match_result = self.find_matching_member_for_cluster(
                cluster_reg_ids, reg_lookup, members_list
            )

            if match_result[0] == 'ambiguous':
                result.ambiguous_skipped += 1
                candidates = match_result[1]
                member_lookup = {m.id: m for m in members_list}
                result.ambiguous_registrations.append({
                    'registrations': [reg_lookup[rid] for rid in cluster_reg_ids],
                    'candidates': [(member_lookup[m_id], conf) for m_id, conf in candidates],
                })
                if self.style:
                    self.log(f'AMBIGUOUS CLUSTER ({len(cluster_reg_ids)} registrations)',
                             self.style.WARNING)
                else:
                    self.log(f'AMBIGUOUS CLUSTER ({len(cluster_reg_ids)} registrations)')
                self.log('  Registrations:')
                for reg_id in cluster_reg_ids:
                    reg = reg_lookup[reg_id]
                    self.log(f'    - ID {reg.identity}: {reg.first_name} {reg.last_name}, '
                             f'DOB {reg.date_of_birth}, {reg.email}, '
                             f'registered {reg.registered_at.date()}')
                self.log('  Candidate members:')
                for m_id, conf in candidates[:5]:
                    member = member_lookup[m_id]
                    self.log(f'    - Member #{member.id}: {member.first_name} {member.last_name}, '
                             f'DOB {member.date_of_birth}, {member.email} '
                             f'(confidence: {conf:.2f})')
                self.log('')
                continue

            member, confidence = match_result

            if member is None:
                if not dry_run:
                    member = self.create_member_from_registration(
                        most_recent_reg, earliest_reg
                    )
                    for reg_id in cluster_reg_ids:
                        reg = reg_lookup[reg_id]
                        reg.matched_member = member
                        reg.save(update_fields=['matched_member'])
                    members_list.append(member)
                result.new_members_created += 1
                result.registrations_linked += len(cluster_reg_ids)
                self.log_debug(f'Created member: {most_recent_reg.first_name} '
                               f'{most_recent_reg.last_name} '
                               f'({len(cluster_reg_ids)} registrations)')
            else:
                if not dry_run:
                    self.update_member_from_registration(member, most_recent_reg)
                    self.update_cohort_if_earlier(member, earliest_reg)
                    for reg_id in cluster_reg_ids:
                        reg = reg_lookup[reg_id]
                        reg.matched_member = member
                        reg.save(update_fields=['matched_member'])
                result.members_updated += 1
                result.registrations_linked += len(cluster_reg_ids)
                self.log_debug(f'Matched cluster: {most_recent_reg.first_name} '
                               f'{most_recent_reg.last_name} -> {member.first_name} '
                               f'{member.last_name} ({len(cluster_reg_ids)} registrations, '
                               f'confidence: {confidence:.2f})')

        self.log('Phase 3: Updating last registration years...')
        if not dry_run:
            years_updated = self.update_last_registration_years()
            self.log(f'Updated last_registration_year for {years_updated} members')

        return result
