from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from backoffice.models import Route


CSV_TEXT = (
    'Route ID,Route URL,Route name,Tags,Location,Distance,Elevation gain,'
    'Unpaved Percent,View Count,Collections,Created,Created by,'
    'Last Modification Date,Last Modification by,Privacy,Events,Experiences,Is Archived\n'
    '1,https://ridewithgps.com/routes/100,Test Route,,Ottawa,42.0,123,0,0,,'
    '2020-01-01,Tester,2020-01-01,Tester,Public,,,No\n'
)


class FakeResponse:
    def __init__(self, text):
        self.content = text.encode('utf-8')

    def raise_for_status(self):
        pass


class SyncRoutesCommandTests(TestCase):
    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_fetches_csv_and_imports(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)
        out = StringIO()

        # Act
        call_command('syncroutes', '--non-interactive', stdout=out)

        # Assert
        mock_get.assert_called_once()
        self.assertEqual(Route.objects.count(), 1)
        route = Route.objects.first()
        self.assertEqual(route.url, 'https://ridewithgps.com/routes/100')
        self.assertEqual(route.distance, 42)
        self.assertEqual(route.elevation_gain, 123)

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_dry_run_does_not_persist(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act
        call_command('syncroutes', '--non-interactive', '--dry-run', stdout=StringIO())

        # Assert
        self.assertEqual(Route.objects.count(), 0)

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_url_override(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act
        call_command('syncroutes', '--non-interactive', '--url', 'https://example.test/x.csv',
                     stdout=StringIO())

        # Assert
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, 'https://example.test/x.csv')
