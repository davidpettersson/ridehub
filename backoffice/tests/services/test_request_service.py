from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, AnonymousUser

from backoffice.services.request_service import RequestService, RequestDetail


class RequestServiceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.service = RequestService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )

    def test_extract_details_from_authenticated_user(self):
        request = self.factory.post('/register')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.user = self.user

        details = self.service.extract_details(request)

        self.assertIsInstance(details, RequestDetail)
        self.assertEqual(details.ip_address, '192.168.1.100')
        self.assertEqual(details.user_agent, 'Mozilla/5.0')
        self.assertTrue(details.authenticated)

    def test_extract_details_from_anonymous_user(self):
        request = self.factory.post('/register')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.user = AnonymousUser()

        details = self.service.extract_details(request)

        self.assertIsInstance(details, RequestDetail)
        self.assertEqual(details.ip_address, '192.168.1.100')
        self.assertEqual(details.user_agent, 'Mozilla/5.0')
        self.assertFalse(details.authenticated)

    def test_extract_details_with_x_forwarded_for(self):
        request = self.factory.post('/register')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.42, 198.51.100.17'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.user = self.user

        details = self.service.extract_details(request)

        self.assertEqual(details.ip_address, '203.0.113.42')

    def test_extract_details_with_x_forwarded_for_single_ip(self):
        request = self.factory.post('/register')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.42'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.user = self.user

        details = self.service.extract_details(request)

        self.assertEqual(details.ip_address, '203.0.113.42')

    def test_extract_details_strips_whitespace_from_ip(self):
        request = self.factory.post('/register')
        request.META['HTTP_X_FORWARDED_FOR'] = '  203.0.113.42  , 198.51.100.17'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.user = self.user

        details = self.service.extract_details(request)

        self.assertEqual(details.ip_address, '203.0.113.42')

    def test_extract_details_without_user_agent(self):
        request = self.factory.post('/register')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.user = self.user

        details = self.service.extract_details(request)

        self.assertEqual(details.ip_address, '192.168.1.100')
        self.assertIsNone(details.user_agent)
        self.assertTrue(details.authenticated)
