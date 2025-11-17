from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from backoffice.models import Event, Program, UserProfile, Registration


class RegistrationViewPhoneTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=3),
            registration_closes_at=now + timezone.timedelta(days=2),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

    def test_registration_form_initial_data_user_with_profile_and_phone(self):
        # Arrange
        user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )
        # Profile is automatically created by signals, just update the phone
        user.profile.phone = '+1234567890'
        user.profile.save()
        
        self.client.force_login(user)

        # Act
        response = self.client.get(reverse('registration_create', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Test')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'testuser@example.com')
        self.assertEqual(form.initial['phone'], '+1234567890')

    def test_registration_form_initial_data_user_with_profile_no_phone(self):
        # Arrange
        user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )
        # Profile is automatically created by signals with empty phone by default
        
        self.client.force_login(user)

        # Act
        response = self.client.get(reverse('registration_create', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Test')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'testuser@example.com')
        self.assertEqual(form.initial['phone'], '')

    def test_registration_form_initial_data_user_with_empty_phone(self):
        # Arrange
        user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )
        # Profile is automatically created by signals, but let's test with empty phone
        user.profile.phone = ''
        user.profile.save()
        
        self.client.force_login(user)

        # Act
        response = self.client.get(reverse('registration_create', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Test')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'testuser@example.com')
        self.assertEqual(form.initial['phone'], '')

    def test_registration_form_initial_data_anonymous_user(self):
        # Arrange - no user login

        # Act
        response = self.client.get(reverse('registration_create', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertNotIn('first_name', form.initial)
        self.assertNotIn('last_name', form.initial)
        self.assertNotIn('email', form.initial)
        self.assertNotIn('phone', form.initial)

    def test_registration_form_submission_updates_existing_profile(self):
        # Arrange
        user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )
        # Profile is automatically created by signals
        initial_phone = user.profile.phone
        
        self.client.force_login(user)

        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testuser@example.com',
            'phone': '+1987654321',
        }

        # Act
        response = self.client.post(reverse('registration_create', args=[self.event.id]), form_data)

        # Assert
        self.assertEqual(response.status_code, 302)  # Redirect to success page
        
        # Check that the profile was updated with the new phone number
        user.refresh_from_db()
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(str(user.profile.phone), '+1987654321')

    def test_registration_form_stores_phone_in_registration_record(self):
        # Arrange
        user = User.objects.create_user(
            username='phonetest@example.com',
            email='phonetest@example.com',
            first_name='Phone',
            last_name='Test'
        )
        
        self.client.force_login(user)

        form_data = {
            'first_name': 'Phone',
            'last_name': 'Test', 
            'email': 'phonetest@example.com',
            'phone': '+1555123456',
        }

        # Act
        response = self.client.post(reverse('registration_create', args=[self.event.id]), form_data)

        # Assert
        self.assertEqual(response.status_code, 302)  # Redirect to success page
        
        # Check that a registration was created
        from backoffice.models import Registration
        registrations = Registration.objects.filter(user=user, event=self.event)
        self.assertEqual(registrations.count(), 1)
        
        # Check that the registration record has the phone number
        registration = registrations.first()
        self.assertEqual(str(registration.phone), '+1555123456')
        
        # Also verify the user profile was updated
        user.refresh_from_db()
        self.assertEqual(str(user.profile.phone), '+1555123456')

    def test_registration_form_stores_phone_for_anonymous_user(self):
        # Arrange - no user login (anonymous registration)
        form_data = {
            'first_name': 'Anonymous',
            'last_name': 'User',
            'email': 'anonymous@example.com',
            'phone': '+1555987654',
        }

        # Act
        response = self.client.post(reverse('registration_create', args=[self.event.id]), form_data)

        # Assert
        self.assertEqual(response.status_code, 302)  # Redirect to success page
        
        # Check that a registration was created
        from backoffice.models import Registration
        registrations = Registration.objects.filter(email='anonymous@example.com', event=self.event)
        self.assertEqual(registrations.count(), 1)
        
        # Check that the registration record has the phone number
        registration = registrations.first()
        self.assertEqual(str(registration.phone), '+1555987654')
        
        # Verify user was created and profile has phone
        from django.contrib.auth.models import User
        users = User.objects.filter(email='anonymous@example.com')
        self.assertEqual(users.count(), 1)
        user = users.first()
        self.assertEqual(str(user.profile.phone), '+1555987654')


class RegistrationWithdrawAccessControlTests(TestCase):
    def setUp(self):
        now = timezone.now()
        program = Program.objects.create(name="Test Program")

        self.event = Event.objects.create(
            name="Test Event",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        self.user_a = User.objects.create_user(
            username='user_a',
            email='user_a@example.com',
            first_name='User',
            last_name='A'
        )
        self.user_a.profile.phone = '+1234567890'
        self.user_a.profile.save()

        self.user_b = User.objects.create_user(
            username='user_b',
            email='user_b@example.com',
            first_name='User',
            last_name='B'
        )
        self.user_b.profile.phone = '+0987654321'
        self.user_b.profile.save()

        self.registration_a = Registration.objects.create(
            event=self.event,
            user=self.user_a,
            state='confirmed'
        )

        self.registration_b = Registration.objects.create(
            event=self.event,
            user=self.user_b,
            state='confirmed'
        )

    def test_user_can_withdraw_own_registration(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse('registration_withdraw', kwargs={'registration_id': self.registration_a.id})
        )

        self.assertEqual(response.status_code, 302)
        updated_registration = Registration.objects.get(id=self.registration_a.id)
        self.assertEqual(updated_registration.state, 'withdrawn')

    def test_user_cannot_withdraw_other_user_registration(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse('registration_withdraw', kwargs={'registration_id': self.registration_b.id})
        )

        self.assertEqual(response.status_code, 404)
        updated_registration = Registration.objects.get(id=self.registration_b.id)
        self.assertEqual(updated_registration.state, 'confirmed')

    def test_unauthenticated_cannot_withdraw_registration(self):
        response = self.client.post(
            reverse('registration_withdraw', kwargs={'registration_id': self.registration_a.id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        updated_registration = Registration.objects.get(id=self.registration_a.id)
        self.assertEqual(updated_registration.state, 'confirmed')

    def test_withdraw_with_invalid_id_returns_404(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse('registration_withdraw', kwargs={'registration_id': 99999})
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_cannot_withdraw_other_user_registration(self):
        staff_user = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            is_staff=True
        )
        self.client.force_login(staff_user)

        response = self.client.post(
            reverse('registration_withdraw', kwargs={'registration_id': self.registration_a.id})
        )

        self.assertEqual(response.status_code, 404)
        updated_registration = Registration.objects.get(id=self.registration_a.id)
        self.assertEqual(updated_registration.state, 'confirmed')