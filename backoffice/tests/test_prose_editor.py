from django.core.checks import run_checks
from django.test import TestCase


class ProseEditorConfigTestCase(TestCase):
    def test_no_prose_editor_warnings(self):
        # Act
        warnings = [
            w for w in run_checks()
            if w.id in ('django_prose_editor.W001', 'django_prose_editor.W004')
        ]

        # Assert
        self.assertEqual(warnings, [])
