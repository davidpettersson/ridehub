import csv
from dataclasses import dataclass, field
from datetime import timedelta
from io import StringIO
from typing import Callable, Optional

from django.db import transaction
from django.utils import timezone

from backoffice.models import Route


CONFLICT_UPDATE = 'manual_edit_update'
CONFLICT_DELETE = 'manual_edit_delete'

ACTION_OVERWRITE = 'overwrite'
ACTION_SKIP = 'skip'
ACTION_DELETE = 'delete'

MANUAL_EDIT_TOLERANCE = timedelta(seconds=5)


@dataclass
class CsvRow:
    name: str
    url: str
    distance: Optional[int]
    elevation_gain: Optional[int]
    archived: bool


@dataclass
class ImportStats:
    imported: int = 0
    updated: int = 0
    archived: int = 0
    unarchived: int = 0
    deleted: int = 0
    undeleted: int = 0
    unchanged: int = 0
    skipped_invalid: int = 0
    conflicts_skipped: int = 0
    conflicts_resolved: int = 0
    warnings: list = field(default_factory=list)


ConflictCallback = Callable[[Route, Optional[CsvRow], str], str]


class RouteImportService:
    def import_from_csv_text(
        self,
        text: str,
        *,
        on_conflict: Optional[ConflictCallback] = None,
        dry_run: bool = False,
    ) -> ImportStats:
        rows = self._parse_csv(text)
        return self._apply(rows, on_conflict=on_conflict, dry_run=dry_run)

    def _parse_csv(self, text: str) -> list[CsvRow]:
        reader = csv.DictReader(StringIO(text))
        rows: list[CsvRow] = []
        for raw in reader:
            name = (raw.get('Route name') or '').strip()
            url = (raw.get('Route URL') or '').strip()
            if not name or not url:
                continue
            rows.append(
                CsvRow(
                    name=name,
                    url=url,
                    distance=self._to_int(raw.get('Distance')),
                    elevation_gain=self._to_int(raw.get('Elevation gain')),
                    archived=(raw.get('Is Archived') or '').strip().lower() == 'yes',
                )
            )
        return rows

    @staticmethod
    def _to_int(value: Optional[str]) -> Optional[int]:
        if not value or not value.strip():
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_manually_edited(route: Route) -> bool:
        if route.last_imported_at is None:
            return False
        return route.updated_at > route.last_imported_at + MANUAL_EDIT_TOLERANCE

    def _diff(self, route: Route, row: CsvRow) -> dict:
        changes = {}
        if route.name != row.name:
            changes['name'] = row.name
        if row.distance is not None and route.distance != row.distance:
            changes['distance'] = row.distance
        if row.elevation_gain is not None and route.elevation_gain != row.elevation_gain:
            changes['elevation_gain'] = row.elevation_gain
        if route.archived != row.archived:
            changes['archived'] = row.archived
        if route.deleted:
            changes['deleted'] = False
        return changes

    def _apply(
        self,
        rows: list[CsvRow],
        *,
        on_conflict: Optional[ConflictCallback],
        dry_run: bool,
    ) -> ImportStats:
        stats = ImportStats()
        now = timezone.now()
        csv_urls = {row.url for row in rows}

        existing_by_url = {
            r.url: r for r in Route.objects.filter(url__in=csv_urls)
        }

        creates: list[Route] = []
        updates: list[tuple[Route, list[str]]] = []

        for row in rows:
            existing = existing_by_url.get(row.url)
            if existing is None:
                creates.append(
                    Route(
                        name=row.name,
                        url=row.url,
                        distance=row.distance,
                        elevation_gain=row.elevation_gain,
                        archived=row.archived,
                        deleted=False,
                        last_imported_at=now,
                    )
                )
                stats.imported += 1
                if row.archived:
                    stats.archived += 1
                continue

            changes = self._diff(existing, row)
            if not changes:
                stats.unchanged += 1
                continue

            if self._is_manually_edited(existing):
                action = self._resolve_conflict(
                    on_conflict, existing, row, CONFLICT_UPDATE, default=ACTION_SKIP
                )
                if action == ACTION_SKIP:
                    stats.conflicts_skipped += 1
                    continue
                stats.conflicts_resolved += 1

            was_archived = existing.archived
            was_deleted = existing.deleted
            updated_fields = []
            for attr, value in changes.items():
                setattr(existing, attr, value)
                updated_fields.append(attr)
            existing.last_imported_at = now
            updated_fields.append('last_imported_at')
            updates.append((existing, updated_fields))

            stats.updated += 1
            if not was_archived and existing.archived:
                stats.archived += 1
            elif was_archived and not existing.archived:
                stats.unarchived += 1
            if was_deleted and not existing.deleted:
                stats.undeleted += 1

        missing_qs = (
            Route.objects.exclude(url__in=csv_urls)
            .exclude(url__isnull=True)
            .exclude(url='')
            .exclude(deleted=True)
        )
        deletes: list[tuple[Route, list[str]]] = []
        for route in missing_qs:
            if self._is_manually_edited(route):
                action = self._resolve_conflict(
                    on_conflict, route, None, CONFLICT_DELETE, default=ACTION_SKIP
                )
                if action == ACTION_SKIP:
                    stats.conflicts_skipped += 1
                    continue
                stats.conflicts_resolved += 1
            route.deleted = True
            deletes.append((route, ['deleted']))
            stats.deleted += 1

        if dry_run:
            return stats

        with transaction.atomic():
            if creates:
                Route.objects.bulk_create(creates)
            for route, fields_ in updates + deletes:
                route.save(update_fields=fields_)

        return stats

    @staticmethod
    def _resolve_conflict(
        callback: Optional[ConflictCallback],
        route: Route,
        row: Optional[CsvRow],
        conflict_type: str,
        *,
        default: str,
    ) -> str:
        if callback is None:
            return default
        result = callback(route, row, conflict_type)
        if result not in (ACTION_OVERWRITE, ACTION_SKIP, ACTION_DELETE):
            return default
        return result
