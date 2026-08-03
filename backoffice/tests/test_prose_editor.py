from django.core.checks import run_checks
from django.test import TestCase

from backoffice.models import Event


class ProseEditorConfigTestCase(TestCase):
    def test_no_prose_editor_warnings(self):
        # Act
        warnings = [
            w for w in run_checks()
            if w.id in ('django_prose_editor.W001', 'django_prose_editor.W004')
        ]

        # Assert
        self.assertEqual(warnings, [])


class ProseEditorSanitizationTestCase(TestCase):
    def test_blockquote_survives_sanitization(self):
        # Arrange
        field = Event._meta.get_field('description')
        html = '<p>before</p><blockquote><p>quoted</p></blockquote><p>after</p>'

        # Act
        cleaned = field.sanitize(html)

        # Assert
        self.assertEqual(cleaned, html)
