from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backoffice.models import Route
from backoffice.services.route_service import (
    ACTION_DELETE,
    ACTION_OVERWRITE,
    ACTION_SKIP,
    CONFLICT_DELETE,
    CONFLICT_UPDATE,
    RouteImportService,
)


CSV_HEADER = (
    'Route ID,Route URL,Route name,Tags,Location,Distance,Elevation gain,'
    'Unpaved Percent,View Count,Collections,Created,Created by,'
    'Last Modification Date,Last Modification by,Privacy,Events,Experiences,Is Archived'
)


def csv_row(*, url, name, distance='', elevation='', archived='No'):
    return f'1,{url},{name},,Ottawa,{distance},{elevation},0,0,,2020-01-01,Tester,2020-01-01,Tester,Public,,,{archived}'


def make_csv(*rows):
    return '\n'.join([CSV_HEADER, *rows]) + '\n'


class RouteImportServiceTests(TestCase):
    def setUp(self):
        # Arrange
        self.service = RouteImportService()
        self.now = timezone.now()

    def _create_route(self, *, url, name='Existing', distance=100, elevation=200,
                      archived=False, deleted=False, last_imported_at=None):
        route = Route.objects.create(
            name=name,
            url=url,
            distance=distance,
            elevation_gain=elevation,
            archived=archived,
            deleted=deleted,
        )
        if last_imported_at is not None:
            Route.objects.filter(pk=route.pk).update(
                last_imported_at=last_imported_at,
                updated_at=last_imported_at,
            )
        return Route.objects.get(pk=route.pk)

    def test_imports_new_route(self):
        # Arrange
        csv_text = make_csv(csv_row(
            url='https://ridewithgps.com/routes/1', name='New Route',
            distance='100.5', elevation='250',
        ))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.imported, 1)
        route = Route.objects.get(url='https://ridewithgps.com/routes/1')
        self.assertEqual(route.name, 'New Route')
        self.assertEqual(route.distance, 100)
        self.assertEqual(route.elevation_gain, 250)
        self.assertFalse(route.archived)
        self.assertFalse(route.deleted)

    def test_updates_existing_route_when_data_differs(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/2'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=url, name='Old', distance=100, elevation=200, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=url, name='Updated', distance='150', elevation='300'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.updated, 1)
        route = Route.objects.get(url=url)
        self.assertEqual(route.name, 'Updated')
        self.assertEqual(route.distance, 150)
        self.assertEqual(route.elevation_gain, 300)

    def test_unchanged_route_not_counted_as_update(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/3'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=url, name='Same', distance=100, elevation=200, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=url, name='Same', distance='100', elevation='200'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.unchanged, 1)
        self.assertEqual(stats.updated, 0)

    def test_archived_csv_marks_route_archived(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/4'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=url, archived=False, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=url, name='Existing', distance='100', elevation='200', archived='Yes'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.archived, 1)
        self.assertTrue(Route.objects.get(url=url).archived)

    def test_unarchives_when_csv_says_no(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/5'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=url, archived=True, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=url, name='Existing', distance='100', elevation='200', archived='No'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.unarchived, 1)
        self.assertFalse(Route.objects.get(url=url).archived)

    def test_marks_missing_route_deleted(self):
        # Arrange
        keep_url = 'https://ridewithgps.com/routes/6'
        gone_url = 'https://ridewithgps.com/routes/7'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=keep_url, last_imported_at=ts)
        self._create_route(url=gone_url, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=keep_url, name='Existing', distance='100', elevation='200'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.deleted, 1)
        self.assertTrue(Route.objects.get(url=gone_url).deleted)
        self.assertFalse(Route.objects.get(url=keep_url).deleted)

    def test_undeletes_route_that_returns_in_csv(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/8'
        ts = timezone.now() - timedelta(days=1)
        self._create_route(url=url, deleted=True, last_imported_at=ts)
        csv_text = make_csv(csv_row(url=url, name='Existing', distance='100', elevation='200'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.undeleted, 1)
        self.assertFalse(Route.objects.get(url=url).deleted)

    def test_skips_invalid_rows(self):
        # Arrange
        csv_text = make_csv(
            csv_row(url='', name='No URL'),
            csv_row(url='https://ridewithgps.com/routes/9', name=''),
            csv_row(url='https://ridewithgps.com/routes/10', name='Valid', distance='50', elevation='10'),
        )

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.imported, 1)
        self.assertEqual(Route.objects.count(), 1)

    def test_dry_run_does_not_persist(self):
        # Arrange
        csv_text = make_csv(csv_row(
            url='https://ridewithgps.com/routes/11', name='New', distance='50', elevation='10'
        ))

        # Act
        stats = self.service.import_from_csv_text(csv_text, dry_run=True)

        # Assert
        self.assertEqual(stats.imported, 1)
        self.assertEqual(Route.objects.count(), 0)

    def test_manual_edit_conflict_skipped_by_default(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/12'
        old = timezone.now() - timedelta(days=10)
        self._create_route(url=url, name='Manually Renamed', last_imported_at=old)
        Route.objects.filter(url=url).update(updated_at=timezone.now())
        csv_text = make_csv(csv_row(url=url, name='Server Name', distance='100', elevation='200'))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.conflicts_skipped, 1)
        self.assertEqual(stats.updated, 0)
        self.assertEqual(Route.objects.get(url=url).name, 'Manually Renamed')

    def test_manual_edit_conflict_overwrite_via_callback(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/13'
        old = timezone.now() - timedelta(days=10)
        self._create_route(url=url, name='Manually Renamed', last_imported_at=old)
        Route.objects.filter(url=url).update(updated_at=timezone.now())
        csv_text = make_csv(csv_row(url=url, name='Server Name', distance='100', elevation='200'))
        seen = []

        def cb(route, row, conflict_type):
            seen.append(conflict_type)
            return ACTION_OVERWRITE

        # Act
        stats = self.service.import_from_csv_text(csv_text, on_conflict=cb)

        # Assert
        self.assertEqual(seen, [CONFLICT_UPDATE])
        self.assertEqual(stats.conflicts_resolved, 1)
        self.assertEqual(stats.updated, 1)
        self.assertEqual(Route.objects.get(url=url).name, 'Server Name')

    def test_manual_edit_conflict_for_deletion_skipped(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/14'
        old = timezone.now() - timedelta(days=10)
        self._create_route(url=url, name='Locally Edited', last_imported_at=old)
        Route.objects.filter(url=url).update(updated_at=timezone.now())
        csv_text = make_csv(csv_row(
            url='https://ridewithgps.com/routes/other', name='Other',
            distance='100', elevation='200',
        ))

        # Act
        stats = self.service.import_from_csv_text(csv_text)

        # Assert
        self.assertEqual(stats.conflicts_skipped, 1)
        self.assertEqual(stats.deleted, 0)
        self.assertFalse(Route.objects.get(url=url).deleted)

    def test_manual_edit_conflict_for_deletion_callback_delete(self):
        # Arrange
        url = 'https://ridewithgps.com/routes/15'
        old = timezone.now() - timedelta(days=10)
        self._create_route(url=url, name='Locally Edited', last_imported_at=old)
        Route.objects.filter(url=url).update(updated_at=timezone.now())
        csv_text = make_csv(csv_row(
            url='https://ridewithgps.com/routes/other', name='Other',
            distance='100', elevation='200',
        ))
        seen = []

        def cb(route, row, conflict_type):
            seen.append(conflict_type)
            return ACTION_DELETE

        # Act
        stats = self.service.import_from_csv_text(csv_text, on_conflict=cb)

        # Assert
        self.assertEqual(seen, [CONFLICT_DELETE])
        self.assertEqual(stats.deleted, 1)
        self.assertTrue(Route.objects.get(url=url).deleted)
