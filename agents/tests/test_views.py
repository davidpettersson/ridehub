from django.test import TestCase


class LlmsTxtTestCase(TestCase):
    def test_returns_200_with_plain_text(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_contains_site_title_and_summary(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        content = response.content.decode()
        self.assertIn('# Ottawa Bicycle Club', content)
        self.assertIn('non-commercial', content)

    def test_contains_event_links(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        content = response.content.decode()
        self.assertIn('/upcoming', content)
        self.assertIn('/events.ics', content)
