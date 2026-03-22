from django.core.signing import TimestampSigner
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.core import mail

from backoffice.models import Event, Program, UserProfile, Registration, Ride, Route, SpeedRange
from backoffice.services.registration_service import VERIFICATION_TOKEN_SALT


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
        user.profile.phone = '+16135550100'
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
        self.assertEqual(form.initial['phone'], '+16135550100')

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
            'phone': '+16139876543',
        }

        # Act
        response = self.client.post(reverse('registration_create', args=[self.event.id]), form_data)

        # Assert
        self.assertEqual(response.status_code, 302)  # Redirect to success page
        
        # Check that the profile was updated with the new phone number
        user.refresh_from_db()
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(str(user.profile.phone), '+16139876543')

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
            'phone': '+16135551234',
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
        self.assertEqual(str(registration.phone), '+16135551234')
        
        # Also verify the user profile was updated
        user.refresh_from_db()
        self.assertEqual(str(user.profile.phone), '+16135551234')

    def test_registration_form_stores_phone_for_anonymous_user(self):
        # Arrange - no user login (anonymous registration)
        form_data = {
            'first_name': 'Anonymous',
            'last_name': 'User',
            'email': 'anonymous@example.com',
            'phone': '+16135559876',
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
        self.assertEqual(str(registration.phone), '+16135559876')
        
        # Verify user was created and profile has phone
        from django.contrib.auth.models import User
        users = User.objects.filter(email='anonymous@example.com')
        self.assertEqual(users.count(), 1)
        user = users.first()
        self.assertEqual(str(user.profile.phone), '+16135559876')


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
        self.user_a.profile.phone = '+16135550100'
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


class RegistrationCreateErrorCaseTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")

    def test_registration_returns_400_for_cancelled_event(self):
        event = Event.objects.create(
            name="Cancelled Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
        )
        event.cancel()
        event.save()

        response = self.client.get(reverse('registration_create', args=[event.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Event is cancelled', response.content)

    def test_registration_returns_400_for_archived_event(self):
        event = Event.objects.create(
            name="Archived Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
        )
        event.archive()
        event.save()

        response = self.client.get(reverse('registration_create', args=[event.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Event is archived', response.content)

    def test_registration_returns_400_when_registration_closed(self):
        event = Event.objects.create(
            name="Closed Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() - timezone.timedelta(days=1)
        )

        response = self.client.get(reverse('registration_create', args=[event.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Registration is closed', response.content)

    def test_registration_returns_400_for_external_registration_url(self):
        event = Event.objects.create(
            name="External Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            external_registration_url='https://example.com/register'
        )

        response = self.client.get(reverse('registration_create', args=[event.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Event uses external registration', response.content)

    def test_registration_returns_400_when_at_capacity(self):
        event = Event.objects.create(
            name="Full Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            registration_limit=1
        )
        user = User.objects.create_user(username='existinguser', email='existing@example.com')
        registration = Registration.objects.create(
            user=user,
            event=event,
            name="Existing User",
            first_name="Existing",
            last_name="User",
            email="existing@example.com"
        )
        registration.confirm()
        registration.save()

        response = self.client.get(reverse('registration_create', args=[event.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Event has reached capacity', response.content)

    def test_registration_returns_404_for_nonexistent_event(self):
        response = self.client.get(reverse('registration_create', args=[99999]))

        self.assertEqual(response.status_code, 404)

    def test_post_registration_returns_400_for_cancelled_event(self):
        event = Event.objects.create(
            name="Cancelled Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
        )
        event.cancel()
        event.save()

        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+16135550100',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Registration.objects.filter(event=event).count(), 0)


class RegistrationFullFlowTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.route = Route.objects.create(name="Test Route")
        mail.outbox = []

    def test_basic_registration_flow_anonymous_requires_verification(self):
        event = Event.objects.create(
            name="Simple Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testuser@example.com',
            'phone': '+16135550100',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)
        self.assertIn('verification-sent', response.url)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.first_name, 'Test')
        self.assertEqual(registration.last_name, 'User')
        self.assertEqual(registration.email, 'testuser@example.com')
        self.assertEqual(registration.state, Registration.STATE_UNVERIFIED)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['testuser@example.com'])

    def test_registration_with_ride_and_speed_range(self):
        event = Event.objects.create(
            name="Ride Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )
        ride = Ride.objects.create(name="Morning Ride", event=event, route=self.route)
        speed_range = SpeedRange.objects.create(lower_limit=20, upper_limit=25)
        ride.speed_ranges.add(speed_range)

        form_data = {
            'first_name': 'Rider',
            'last_name': 'Test',
            'email': 'rider@example.com',
            'phone': '+16135550100',
            'ride': ride.id,
            'speed_range_preference': speed_range.id,
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.ride, ride)
        self.assertEqual(registration.speed_range_preference, speed_range)
        self.assertEqual(registration.state, Registration.STATE_UNVERIFIED)

    def test_registration_with_emergency_contact(self):
        event = Event.objects.create(
            name="Emergency Contact Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=True,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        form_data = {
            'first_name': 'Emergency',
            'last_name': 'Test',
            'email': 'emergency@example.com',
            'phone': '+16135550100',
            'emergency_contact_name': 'John Doe',
            'emergency_contact_phone': '+9876543210',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.emergency_contact_name, 'John Doe')
        self.assertEqual(registration.emergency_contact_phone, '+9876543210')
        self.assertEqual(registration.state, Registration.STATE_UNVERIFIED)

    def test_registration_with_ride_leader_preference(self):
        event = Event.objects.create(
            name="Ride Leader Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=True,
            requires_membership=False
        )

        form_data = {
            'first_name': 'Leader',
            'last_name': 'Test',
            'email': 'leader@example.com',
            'phone': '+16135550100',
            'ride_leader_preference': Registration.RideLeaderPreference.YES,
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.ride_leader_preference, Registration.RideLeaderPreference.YES)
        self.assertEqual(registration.state, Registration.STATE_UNVERIFIED)

    def test_registration_with_all_options(self):
        event = Event.objects.create(
            name="Full Options Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=True,
            ride_leaders_wanted=True,
            requires_membership=False
        )
        ride = Ride.objects.create(name="Full Ride", event=event, route=self.route)
        speed_range = SpeedRange.objects.create(lower_limit=25, upper_limit=30)
        ride.speed_ranges.add(speed_range)

        form_data = {
            'first_name': 'Full',
            'last_name': 'Test',
            'email': 'full@example.com',
            'phone': '+16135550100',
            'ride': ride.id,
            'speed_range_preference': speed_range.id,
            'emergency_contact_name': 'Emergency Person',
            'emergency_contact_phone': '+9999999999',
            'ride_leader_preference': Registration.RideLeaderPreference.YES,
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.first_name, 'Full')
        self.assertEqual(registration.last_name, 'Test')
        self.assertEqual(registration.email, 'full@example.com')
        self.assertEqual(registration.ride, ride)
        self.assertEqual(registration.speed_range_preference, speed_range)
        self.assertEqual(registration.emergency_contact_name, 'Emergency Person')
        self.assertEqual(registration.emergency_contact_phone, '+9999999999')
        self.assertEqual(registration.ride_leader_preference, Registration.RideLeaderPreference.YES)
        self.assertEqual(registration.state, Registration.STATE_UNVERIFIED)

        self.assertEqual(len(mail.outbox), 1)

    def test_authenticated_user_registration_flow(self):
        user = User.objects.create_user(
            username='authuser',
            email='authuser@example.com',
            first_name='Auth',
            last_name='User'
        )
        user.profile.phone = '+16135550100'
        user.profile.save()

        event = Event.objects.create(
            name="Auth Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        self.client.force_login(user)

        response = self.client.get(reverse('registration_create', args=[event.id]))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Auth')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'authuser@example.com')

        form_data = {
            'first_name': 'Auth',
            'last_name': 'User',
            'email': 'authuser@example.com',
            'phone': '+16135550100',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.user, user)
        self.assertEqual(registration.state, Registration.STATE_CONFIRMED)

    def test_registration_creates_user_for_anonymous(self):
        event = Event.objects.create(
            name="Anon Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        form_data = {
            'first_name': 'New',
            'last_name': 'Person',
            'email': 'newperson@example.com',
            'phone': '+16135550100',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)

        self.assertTrue(User.objects.filter(email='newperson@example.com').exists())
        user = User.objects.get(email='newperson@example.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'Person')

        registration = Registration.objects.get(event=event)
        self.assertEqual(registration.user, user)

    def test_anonymous_registration_redirects_to_verification_sent(self):
        event = Event.objects.create(
            name="Redirect Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        form_data = {
            'first_name': 'Redirect',
            'last_name': 'Test',
            'email': 'redirect@example.com',
            'phone': '+16135550100',
        }

        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        self.assertEqual(response.status_code, 302)
        self.assertIn('verification-sent', response.url)

    def test_verified_user_redirects_to_submitted(self):
        # Arrange
        user = User.objects.create_user(
            username='verified@example.com',
            email='verified@example.com',
            first_name='Verified',
            last_name='User',
        )
        user.profile.email_verified = True
        user.profile.save()

        event = Event.objects.create(
            name="Verified Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False,
        )

        form_data = {
            'first_name': 'Verified',
            'last_name': 'User',
            'email': 'verified@example.com',
            'phone': '+16135550100',
        }

        # Act
        response = self.client.post(reverse('registration_create', args=[event.id]), form_data)

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('submitted', response.url)


class RegistrationVerifyViewTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
        )
        self.user = User.objects.create_user(
            username='verify@example.com',
            email='verify@example.com',
            first_name='Verify',
            last_name='User',
        )
        self.registration = Registration.objects.create(
            event=self.event,
            user=self.user,
            name="Verify User",
            first_name="Verify",
            last_name="User",
            email="verify@example.com",
        )
        self.registration.hold_for_verification()
        self.registration.save()
        mail.outbox = []

    def test_verify_valid_token_confirms_and_logs_in(self):
        # Arrange
        signer = TimestampSigner(salt=VERIFICATION_TOKEN_SALT)
        token = signer.sign(str(self.registration.id))

        # Act
        response = self.client.get(reverse('registration_verify') + f'?token={token}')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/registrations/verification_success.html')
        updated = Registration.objects.get(pk=self.registration.pk)
        self.assertEqual(updated.state, Registration.STATE_CONFIRMED)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_verify_invalid_token_shows_error(self):
        # Act
        response = self.client.get(reverse('registration_verify') + '?token=invalid-token')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/registrations/verification_failed.html')
        self.assertEqual(response.context['reason'], 'invalid')

    def test_verify_missing_token_shows_error(self):
        # Act
        response = self.client.get(reverse('registration_verify'))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/registrations/verification_failed.html')

    def test_verify_already_confirmed_shows_not_found(self):
        # Arrange
        self.registration.confirm()
        self.registration.save()
        signer = TimestampSigner(salt=VERIFICATION_TOKEN_SALT)
        token = signer.sign(str(self.registration.id))

        # Act
        response = self.client.get(reverse('registration_verify') + f'?token={token}')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/registrations/verification_failed.html')
        self.assertEqual(response.context['reason'], 'not_found')

    def test_verification_sent_page_renders(self):
        # Act
        response = self.client.get(reverse('registration_verification_sent'))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/registrations/verification_sent.html')