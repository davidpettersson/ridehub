from django.contrib.auth.models import User
from django.test import TestCase

from content.models import Page


class PageViewTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password='password123',
            is_staff=True,
        )

        self.published_page = Page.objects.create(
            slug='user-guide',
            title='User Guide',
            body='# User Guide\n\nHow to use the app.',
            published=True,
        )

        self.draft_page = Page.objects.create(
            slug='draft-page',
            title='Draft Page',
            body='Not ready yet.',
            published=False,
        )

    def test_anon_sees_published_page(self):
        # Act
        response = self.client.get('/pages/user-guide')

        # Assert
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('User Guide', content)
        self.assertIn('How to use the app', content)

    def test_anon_gets_404_for_unpublished_page(self):
        # Act
        response = self.client.get('/pages/draft-page')

        # Assert
        self.assertEqual(response.status_code, 404)

    def test_anon_gets_404_for_unknown_slug(self):
        # Act
        response = self.client.get('/pages/does-not-exist')

        # Assert
        self.assertEqual(response.status_code, 404)

    def test_staff_sees_unpublished_page(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get('/pages/draft-page')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('Not ready yet', response.content.decode())

    def test_help_route_renders_help_slug(self):
        # Arrange
        Page.objects.create(slug='help', title='Help', body='Start here.', published=True)

        # Act
        response = self.client.get('/help')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('Start here', response.content.decode())

    def test_emergency_route_renders_emergency_slug(self):
        # Arrange
        Page.objects.create(slug='emergency', title='Emergency', body='Call 911.', published=True)

        # Act
        response = self.client.get('/emergency')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('Call 911', response.content.decode())

    def test_body_html_strips_script_tags(self):
        # Arrange
        page = Page.objects.create(
            slug='xss-test',
            title='XSS Test',
            body='Hello <script>alert(1)</script> world',
            published=True,
        )

        # Act
        response = self.client.get('/pages/xss-test')

        # Assert
        content = response.content.decode()
        self.assertNotIn('alert(1)', content)
        self.assertIn('Hello', content)
        self.assertIn('world', content)
