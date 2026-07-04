from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from audit.models import AuditEvent
from backoffice.models import Route


CSV_TEXT = (
    'Route ID,Route URL,Route name,Tags,Location,Distance,Elevation gain,'
    'Unpaved Percent,View Count,Collections,Created,Created by,'
    'Last Modification Date,Last Modification by,Privacy,Events,Experiences,Is Archived\n'
    '1,https://ridewithgps.com/routes/100,Test Route,,Ottawa,42.0,123,0,0,,'
    '2020-01-01,Tester,2020-01-01,Tester,Public,,,No\n'
)


class FakeResponse:
    def __init__(self, text, content_type='text/plain'):
        self.content = text.encode('utf-8')
        self.headers = {'Content-Type': content_type}

    def raise_for_status(self):
        pass


class SyncRoutesCommandTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username='importer', email='importer@example.com', password='password123'
        )

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_fetches_csv_and_imports(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)
        out = StringIO()

        # Act
        call_command('syncroutes', '--non-interactive', '--actor', self.actor.email, stdout=out)

        # Assert
        mock_get.assert_called_once()
        self.assertEqual(Route.objects.count(), 1)
        route = Route.objects.first()
        self.assertEqual(route.url, 'https://ridewithgps.com/routes/100')
        self.assertEqual(route.distance, 42)
        self.assertEqual(route.elevation_gain, 123)

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_import_logs_audit_event_per_row(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act
        call_command('syncroutes', '--non-interactive', '--actor', self.actor.email, stdout=StringIO())

        # Assert
        audit_event = AuditEvent.objects.get()
        self.assertEqual(audit_event.subject, self.actor)
        self.assertEqual(audit_event.action, 'created')
        self.assertEqual(audit_event.target, Route.objects.first())

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_unknown_actor_aborts_with_command_error(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act / Assert
        with self.assertRaises(CommandError):
            call_command('syncroutes', '--non-interactive', '--actor', 'nobody@example.com',
                         stdout=StringIO())
        self.assertEqual(Route.objects.count(), 0)

    def test_missing_actor_aborts_with_command_error(self):
        # Act / Assert
        with self.assertRaises(CommandError):
            call_command('syncroutes', '--non-interactive', stdout=StringIO())

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_dry_run_does_not_persist(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act
        call_command('syncroutes', '--non-interactive', '--dry-run', '--actor', self.actor.email,
                     stdout=StringIO())

        # Assert
        self.assertEqual(Route.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_url_override(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse(CSV_TEXT)

        # Act
        call_command('syncroutes', '--non-interactive', '--url', 'https://example.test/x.csv',
                     '--actor', self.actor.email, stdout=StringIO())

        # Assert
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, 'https://example.test/x.csv')

    @patch('backoffice.management.commands.syncroutes.requests.get')
    def test_html_response_aborts_with_command_error(self, mock_get):
        # Arrange
        mock_get.return_value = FakeResponse('<html>login</html>', content_type='text/html; charset=utf-8')

        # Act / Assert
        with self.assertRaises(CommandError):
            call_command('syncroutes', '--non-interactive', '--actor', self.actor.email,
                         stdout=StringIO())
