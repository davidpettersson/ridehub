from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from waffle.testutils import override_flag

from backoffice.models import Event, Program, UserMembershipNumber


class MembershipNumberRegistrationFlowTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Membership Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=True,
        )
        self.form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testflow@example.com',
            'phone': '+16135550100',
            'membership_confirmation': 'on',
        }

    @override_flag('capture_membership_number', active=False)
    def test_flag_off_redirects_to_submitted(self):
        # Arrange
        user = User.objects.create_user(
            username='testflow@example.com',
            email='testflow@example.com',
            first_name='Test',
            last_name='User',
        )
        user.profile.email_verified = True
        user.profile.save()
        self.client.force_login(user)

        # Act
        response = self.client.post(
            reverse('registration_create', args=[self.event.id]),
            self.form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)

    @override_flag('capture_membership_number', active=True)
    def test_flag_on_anonymous_user_redirects_to_verification_sent(self):
        # Act
        response = self.client.post(
            reverse('registration_create', args=[self.event.id]),
            self.form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('verification-sent', response.url)

    @override_flag('capture_membership_number', active=True)
    def test_flag_on_authenticated_user_redirects_to_interstitial(self):
        # Arrange
        user = User.objects.create_user(
            username='testflow@example.com',
            email='testflow@example.com',
            first_name='Test',
            last_name='User',
        )
        user.profile.phone = '+16135550100'
        user.profile.save()
        self.client.force_login(user)

        # Act
        response = self.client.post(
            reverse('registration_create', args=[self.event.id]),
            self.form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('membership-number', response.url)

    @override_flag('capture_membership_number', active=True)
    def test_flag_on_authenticated_no_membership_redirects_to_interstitial(self):
        # Arrange
        user = User.objects.create_user(
            username='testflow@example.com',
            email='testflow@example.com',
            first_name='Test',
            last_name='User',
        )
        user.profile.phone = '+16135550100'
        user.profile.save()
        self.client.force_login(user)

        # Act
        response = self.client.post(
            reverse('registration_create', args=[self.event.id]),
            self.form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('membership-number', response.url)

    @override_flag('capture_membership_number', active=True)
    def test_flag_on_authenticated_with_membership_skips_interstitial(self):
        # Arrange
        user = User.objects.create_user(
            username='testflow@example.com',
            email='testflow@example.com',
            first_name='Test',
            last_name='User',
        )
        user.profile.phone = '+16135550100'
        user.profile.save()
        UserMembershipNumber.objects.create(
            user=user, number='OBC-123', year=timezone.now().year
        )
        self.client.force_login(user)

        # Act
        response = self.client.post(
            reverse('registration_create', args=[self.event.id]),
            self.form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)

    @override_flag('capture_membership_number', active=True)
    def test_flag_on_event_not_requiring_membership_redirects_to_submitted(self):
        # Arrange
        user = User.objects.create_user(
            username='nomembership@example.com',
            email='nomembership@example.com',
            first_name='Test',
            last_name='User',
        )
        user.profile.email_verified = True
        user.profile.save()
        self.client.force_login(user)

        event = Event.objects.create(
            name="No Membership Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False,
        )
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'nomembership@example.com',
            'phone': '+16135550100',
        }

        # Act
        response = self.client.post(
            reverse('registration_create', args=[event.id]),
            form_data,
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)


@override_flag('capture_membership_number', active=True)
class MembershipNumberInterstitialTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Membership Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_membership=True,
        )
        self.user = User.objects.create_user(
            username='interstitial@example.com',
            email='interstitial@example.com',
            first_name='Test',
            last_name='User',
        )

    def test_get_renders_form(self):
        # Arrange
        session = self.client.session
        session['membership_capture_user_id'] = self.user.id
        session.save()

        # Act
        response = self.client.get(
            reverse('membership_number_capture', args=[self.event.id])
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'membership_number')

    def test_post_with_number_saves_and_redirects(self):
        # Arrange
        session = self.client.session
        session['membership_capture_user_id'] = self.user.id
        session.save()

        # Act
        response = self.client.post(
            reverse('membership_number_capture', args=[self.event.id]),
            {'membership_number': 'OBC-99999'},
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)
        self.assertTrue(
            UserMembershipNumber.objects.filter(user=self.user, number='OBC-99999').exists()
        )

    def test_post_skip_redirects_without_saving(self):
        # Arrange
        session = self.client.session
        session['membership_capture_user_id'] = self.user.id
        session.save()

        # Act
        response = self.client.post(
            reverse('membership_number_capture', args=[self.event.id]),
            {'skip': '1'},
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)
        self.assertEqual(UserMembershipNumber.objects.filter(user=self.user).count(), 0)

    def test_get_without_session_redirects_to_submitted(self):
        # Act
        response = self.client.get(
            reverse('membership_number_capture', args=[self.event.id])
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)


class ProfileMembershipNumberTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='profile@example.com',
            email='profile@example.com',
            first_name='Profile',
            last_name='User',
        )
        self.client.force_login(self.user)

    @override_flag('capture_membership_number', active=True)
    def test_profile_shows_membership_number_when_exists(self):
        # Arrange
        UserMembershipNumber.objects.create(
            user=self.user, number='OBC-111', year=timezone.now().year
        )

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertContains(response, 'OBC-111')

    @override_flag('capture_membership_number', active=True)
    def test_profile_shows_enter_link_when_no_number(self):
        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertContains(response, 'Enter membership number')

    @override_flag('capture_membership_number', active=False)
    def test_profile_hides_section_when_flag_off(self):
        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertNotContains(response, 'Membership number')

    @override_flag('capture_membership_number', active=True)
    def test_profile_post_saves_membership_number(self):
        # Act
        response = self.client.post(
            reverse('profile_membership_number'),
            {'membership_number': 'OBC-222'},
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            UserMembershipNumber.objects.filter(user=self.user, number='OBC-222').exists()
        )

    @override_flag('capture_membership_number', active=True)
    def test_profile_post_rejects_duplicate(self):
        # Arrange
        UserMembershipNumber.objects.create(
            user=self.user, number='OBC-EXISTING', year=timezone.now().year
        )

        # Act
        self.client.post(
            reverse('profile_membership_number'),
            {'membership_number': 'OBC-DUPLICATE'},
        )

        # Assert
        self.assertFalse(
            UserMembershipNumber.objects.filter(user=self.user, number='OBC-DUPLICATE').exists()
        )
        self.assertEqual(
            UserMembershipNumber.objects.filter(user=self.user, year=timezone.now().year).count(), 1
        )
