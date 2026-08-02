from django.test import TestCase
from sentry_sdk.integrations.celery import CeleryIntegration

from ridehub.settings import _sentry_integrations


class SentryIntegrationTests(TestCase):

    def _celery_integration(self):
        return next(i for i in _sentry_integrations() if isinstance(i, CeleryIntegration))

    def test_celery_integration_is_configured(self):
        # Act
        integration = self._celery_integration()

        # Assert
        self.assertIsNotNone(integration)

    def test_beat_tasks_are_monitored(self):
        # Act
        integration = self._celery_integration()

        # Assert
        self.assertTrue(integration.monitor_beat_tasks)

    def test_no_beat_tasks_are_excluded_from_monitoring(self):
        # Act
        integration = self._celery_integration()

        # Assert
        self.assertIsNone(integration.exclude_beat_tasks)
