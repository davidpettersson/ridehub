from django.db import IntegrityError
from django.test import TestCase

from backoffice.models import Route


class RouteModelTests(TestCase):
    def test_blank_url_normalized_to_none_on_save(self):
        # Arrange
        route = Route(name='No URL', url='')

        # Act
        route.save()

        # Assert
        route.refresh_from_db()
        self.assertIsNone(route.url)

    def test_multiple_routes_with_blank_url_allowed(self):
        # Arrange
        Route.objects.create(name='First', url='')

        # Act
        Route.objects.create(name='Second', url='')

        # Assert
        self.assertEqual(Route.objects.filter(url__isnull=True).count(), 2)

    def test_duplicate_non_null_url_rejected(self):
        # Arrange
        Route.objects.create(name='First', url='https://ridewithgps.com/routes/1')

        # Act / Assert
        with self.assertRaises(IntegrityError):
            Route.objects.create(name='Second', url='https://ridewithgps.com/routes/1')

    def test_ride_with_gps_id_returns_none_when_url_blank(self):
        # Arrange
        route = Route(name='No URL', url='')

        # Act / Assert
        self.assertIsNone(route.ride_with_gps_id())

    def test_ride_with_gps_id_returns_none_when_url_null(self):
        # Arrange
        route = Route(name='No URL', url=None)

        # Act / Assert
        self.assertIsNone(route.ride_with_gps_id())

    def test_ride_with_gps_id_returns_trailing_segment(self):
        # Arrange
        route = Route(name='Has URL', url='https://ridewithgps.com/routes/12345')

        # Act / Assert
        self.assertEqual(route.ride_with_gps_id(), '12345')
