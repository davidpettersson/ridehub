from django.test import TestCase


class RobotsTxtTest(TestCase):
    def test_returns_200_with_plain_text(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_contains_disallow_for_registrations(self):
        response = self.client.get("/robots.txt")
        self.assertIn("Disallow: /events/*/registrations", response.content.decode())

    def test_contains_non_commercial_comment(self):
        response = self.client.get("/robots.txt")
        self.assertIn("Content on this site is for non-commercial usage only.", response.content.decode())
