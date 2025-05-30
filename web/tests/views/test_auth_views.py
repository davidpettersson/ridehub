from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from sesame.utils import get_query_string
from web.utils import get_sesame_max_age_minutes, is_sesame_one_time


class AuthViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password123', first_name='Test')
        self.login_form_url = reverse('login_form')
        self.logout_url = reverse('logout')
        self.profile_url = reverse('profile') # LOGIN_REDIRECT_URL is '/profile'

    def test_login_form_view_get(self):
        # Arrange / Act
        response = self.client.get(self.login_form_url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_form.html')
        # Check for "Log in" text in the header for unauthenticated user
        # The user recently changed the link to use 'login_form' and text to "Log in"
        self.assertContains(response, f'<a href="{self.login_form_url}" class="text-white hover:text-gray-200 transition-colors duration-200 inline-flex items-center">\n                Log in\n            </a>', html=True)


    def test_logout_view_authenticated_user(self):
        # Arrange
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.profile_url) # Go to a page that requires login
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertContains(response, f'<span class="mr-2">{self.user.first_name}</span>')


        # Act
        logout_response = self.client.get(self.logout_url)

        # Assert
        # After logout, user is typically redirected. Default is LOGIN_URL or LOGOUT_REDIRECT_URL if set.
        # login_url in settings.py is '/login/' which sesame.views.LoginView maps to 'login' name.
        # logout_view redirects to LOGIN_URL
        expected_redirect_url = reverse('event_list')
        self.assertRedirects(logout_response, expected_redirect_url, fetch_redirect_response=False) # Don't follow the redirect yet

        # Verify user is logged out by trying to access a protected page or checking session
        # For simplicity, we'll check if the user is anonymous on a new request to login_form_url
        response_after_logout = self.client.get(self.login_form_url)
        self.assertFalse(response_after_logout.context['user'].is_authenticated)
        # Check that the "Log in" link is present again
        self.assertContains(response_after_logout, f'<a href="{self.login_form_url}" class="text-white hover:text-gray-200 transition-colors duration-200 inline-flex items-center">\n                Log in\n            </a>', html=True)
        # Check that the first name is NOT present
        self.assertNotContains(response_after_logout, f'<span class="mr-2">{self.user.first_name}</span>')


    def test_login_form_view_for_authenticated_user(self):
        # Arrange
        self.client.login(username='testuser', password='password123')

        # Act
        response = self.client.get(self.login_form_url)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_form.html')
        # Should contain a message that user is already logged in and link to profile
        self.assertContains(response, f"You are already logged in as {self.user.email}.")
        self.assertContains(response, f'<a href="{self.profile_url}"')
        # Header should show user's first name
        self.assertContains(response, f'<span class="mr-2">{self.user.first_name}</span>')
        self.assertContains(response, f'<a href="{self.profile_url}"')
        self.assertNotContains(response, f'<a href="{self.login_form_url}" class="text-white hover:text-gray-200 transition-colors duration-200 inline-flex items-center">\n                Log in\n            </a>', html=True)

    def test_login_email_sent_page_shows_validity_info(self):
        # Arrange / Act
        response = self.client.post(self.login_form_url, {'email': self.user.email})
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_email_sent.html')
        
        # Check for dynamic values rendered by template tags
        max_age_minutes = get_sesame_max_age_minutes()
        if max_age_minutes:
            self.assertContains(response, f'The link is valid for <strong>{max_age_minutes} minute')
        
        if is_sesame_one_time():
            self.assertContains(response, 'The link can be used <strong>only once</strong>')
        
        self.assertContains(response, "After clicking the link, you'll be logged in automatically")

    def test_login_email_contains_validity_info(self):
        # Arrange / Act
        response = self.client.post(self.login_form_url, {'email': self.user.email})
        
        # Assert
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        max_age_minutes = get_sesame_max_age_minutes()
        is_one_time = is_sesame_one_time()
        
        # Check HTML version
        html_body = email.alternatives[0][0] if email.alternatives else None
        if html_body:
            if max_age_minutes:
                self.assertIn(f'This link is valid for <strong>{max_age_minutes} minute', html_body)
            if is_one_time:
                self.assertIn('This link can be used <strong>only once</strong>', html_body)
            # Check for profile URL (might be http in test environment)
            self.assertIn('obcrides.ca/profile', html_body)
        
        # Check text version
        if max_age_minutes:
            self.assertIn(f'This link is valid for {max_age_minutes} minute', email.body)
        if is_one_time:
            self.assertIn('This link can be used only once', email.body)
        # Check for profile URL (might be http in test environment)
        self.assertIn('obcrides.ca/profile', email.body)

    def test_expired_link_shows_friendly_error(self):
        # Arrange
        # Create an invalid token URL
        login_url = reverse('login')
        invalid_token_url = login_url + '?sesame=invalid_token_here'
        
        # Act
        response = self.client.get(invalid_token_url)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/login/login_expired.html')
        self.assertContains(response, 'This login link has expired')
        self.assertContains(response, 'Request new login link')
        self.assertContains(response, f'href="{self.login_form_url}"')

    # We are not testing the full sesame login flow (sending email, clicking link) here,
    # as that is more complex and better suited for acceptance tests or integration tests
    # that can mock email sending and handle external interactions.
    # These tests focus on the view behavior given an authentication state. 