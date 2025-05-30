from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, Client
from django.urls import reverse

from web.utils import get_sesame_max_age_minutes, is_sesame_one_time


class LoginFormViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('login_form')

    def test_get_login_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_form.html')
        self.assertContains(response, 'Log in')
        self.assertContains(response, f'href="{self.url}"')


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test'
        )
        self.logout_url = reverse('logout')
        self.profile_url = reverse('profile')
        self.login_form_url = reverse('login_form')

    def test_logout_redirects_to_event_list(self):
        self.client.login(username='testuser', password='password123')

        response = self.client.get(self.logout_url)

        self.assertRedirects(response, reverse('event_list'), fetch_redirect_response=False)

    def test_logout_clears_authentication(self):
        self.client.login(username='testuser', password='password123')

        self.client.get(self.logout_url)
        response = self.client.get(self.login_form_url)

        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, 'Log in')
        self.assertContains(response, f'href="{self.login_form_url}"')
        self.assertNotContains(response, self.user.first_name)


class LoginEmailTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.login_form_url = reverse('login_form')
        self.base_url = 'http://example.com'

    def test_login_email_contains_validity_info(self):
        response = self.client.post(self.login_form_url, {'email': self.user.email})

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        max_age_minutes = get_sesame_max_age_minutes()
        is_one_time = is_sesame_one_time()

        html_body = email.alternatives[0][0] if email.alternatives else None
        if html_body:
            if max_age_minutes:
                self.assertIn(f'{max_age_minutes} minute', html_body)
            if is_one_time:
                self.assertIn('only once', html_body)
            self.assertRegex(html_body, r'https?://[^/]+/profile')

        if max_age_minutes:
            self.assertIn(f'{max_age_minutes} minute', email.body)
        if is_one_time:
            self.assertIn('only once', email.body)
        self.assertRegex(email.body, r'https?://[^/]+/profile')

    def test_login_email_sent_page_shows_validity_info(self):
        response = self.client.post(self.login_form_url, {'email': self.user.email})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_email_sent.html')

        max_age_minutes = get_sesame_max_age_minutes()
        if max_age_minutes:
            self.assertContains(response, f'{max_age_minutes} minute')

        if is_sesame_one_time():
            self.assertContains(response, 'only once')

        self.assertContains(response, "After clicking the link, you'll be logged in automatically")

    def test_expired_link_shows_friendly_error(self):
        login_url = reverse('login')
        invalid_token_url = login_url + '?sesame=invalid_token_here'

        response = self.client.get(invalid_token_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_expired.html')
        self.assertContains(response, 'This login link has expired')
        self.assertContains(response, 'Request new login link')
        self.assertContains(response, f'href="{self.login_form_url}"')
