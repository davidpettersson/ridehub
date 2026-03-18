from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Program, Registration, Ride, Route, SpeedRange


class BaseManageTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")

        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            ends_at=now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False,
        )

        self.route = Route.objects.create(name="Test Route")
        self.ride = Ride.objects.create(event=self.event, route=self.route, ordering=1)
        self.speed_range = SpeedRange.objects.create(lower_limit=25, upper_limit=30)
        self.ride.speed_ranges.add(self.speed_range)

        self.other_speed_range = SpeedRange.objects.create(lower_limit=35, upper_limit=40)

        self.staff_user = User.objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='User',
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username='regular@example.com',
            email='regular@example.com',
            password='password123',
            first_name='Regular',
            last_name='User',
        )

    def _create_confirmed_registration(self, user, ride=None, speed_range=None):
        reg = Registration.objects.create(
            event=self.event,
            user=user,
            name=user.get_full_name(),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone='+16135550100',
            ride=ride,
            speed_range_preference=speed_range,
        )
        reg.confirm()
        reg.save()
        return reg


class ManagePageAccessTests(BaseManageTestCase):
    def test_staff_can_access_manage_page(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registrations_manage.html')

    def test_non_staff_denied_manage_page(self):
        # Arrange
        self.client.login(username='regular@example.com', password='password123')

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected_from_manage_page(self):
        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 302)

    def test_manage_page_shows_all_registration_states(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        confirmed_reg = self._create_confirmed_registration(
            self.regular_user, self.ride, self.speed_range
        )

        withdrawn_user = User.objects.create_user(
            username='withdrawn@example.com', email='withdrawn@example.com',
            password='password123', first_name='Withdrawn', last_name='User',
        )
        withdrawn_reg = self._create_confirmed_registration(
            withdrawn_user, self.ride, self.speed_range
        )
        withdrawn_reg.withdraw()
        withdrawn_reg.save()

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Regular')
        self.assertContains(response, 'Withdrawn')


class StaffWithdrawTests(BaseManageTestCase):
    def test_staff_can_withdraw_confirmed_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(id=reg.id)
        self.assertEqual(reg.state, Registration.STATE_WITHDRAWN)

    def test_non_staff_denied_withdraw(self):
        # Arrange
        self.client.login(username='regular@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_withdraw_sends_email(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        from django.core import mail
        self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('withdrawn', mail.outbox[0].subject.lower())

    def test_get_request_redirects(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(id=reg.id)
        self.assertEqual(reg.state, Registration.STATE_CONFIRMED)


class StaffAddTests(BaseManageTestCase):
    def test_staff_can_access_add_form(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('staff_registration_add', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registration_staff_form.html')

    def test_non_staff_denied_add(self):
        # Arrange
        self.client.login(username='regular@example.com', password='password123')

        # Act
        response = self.client.get(reverse('staff_registration_add', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_staff_can_add_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.state, Registration.STATE_CONFIRMED)
        self.assertEqual(reg.ride, self.ride)

    def test_staff_add_sends_confirmation_email(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        from django.core import mail
        self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
        })

        # Assert
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newrider@example.com', mail.outbox[0].to)

    def test_staff_add_prevents_duplicate(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'Regular',
            'last_name': 'User',
            'email': 'regular@example.com',
            'phone': '+16135550100',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
        })

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already has an active registration')

    def test_staff_add_rejects_speed_range_not_on_ride(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.other_speed_range.id,
        })

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('speed_range_preference', form.errors)
        self.assertIn('Selected speed range is not available for this ride.', form.errors['speed_range_preference'])


class StaffEditTests(BaseManageTestCase):
    def test_staff_can_access_edit_form(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registration_staff_form.html')

    def test_non_staff_denied_edit(self):
        # Arrange
        self.client.login(username='regular@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_staff_can_edit_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(
            reverse('staff_registration_edit', args=[self.event.id, reg.id]),
            {
                'first_name': 'Updated',
                'last_name': 'Name',
                'email': 'regular@example.com',
                'phone': '+16135550100',
                'ride': self.ride.id,
                'speed_range_preference': self.speed_range.id,
            }
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(id=reg.id)
        self.assertEqual(reg.first_name, 'Updated')
        self.assertEqual(reg.last_name, 'Name')
        self.assertEqual(reg.name, 'Updated Name')

    def test_staff_edit_rejects_speed_range_not_on_ride(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(
            reverse('staff_registration_edit', args=[self.event.id, reg.id]),
            {
                'first_name': 'Regular',
                'last_name': 'User',
                'email': 'regular@example.com',
                'phone': '+16135550100',
                'ride': self.ride.id,
                'speed_range_preference': self.other_speed_range.id,
            }
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('speed_range_preference', form.errors)
        self.assertIn('Selected speed range is not available for this ride.', form.errors['speed_range_preference'])

    def test_edit_form_prepopulated_with_registration_data(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Regular')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'regular@example.com')


class StaffAddValidationWithEventRequirementsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")

        self.event = Event.objects.create(
            name="Test Event With Requirements",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            ends_at=now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_emergency_contact=True,
            ride_leaders_wanted=True,
            requires_membership=False,
        )

        self.route = Route.objects.create(name="Test Route")
        self.ride = Ride.objects.create(event=self.event, route=self.route, ordering=1)
        self.speed_range = SpeedRange.objects.create(lower_limit=25, upper_limit=30)
        self.ride.speed_ranges.add(self.speed_range)

        self.staff_user = User.objects.create_user(
            username='staff@example.com', email='staff@example.com',
            password='password123', is_staff=True,
        )

    def test_staff_add_without_emergency_contact_rejected(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'ride_leader_preference': 'n',
        })

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors.get('emergency_contact_name'))

    def test_staff_add_without_ride_leader_preference_rejected(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '6135551234',
        })

        # Assert
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors.get('ride_leader_preference'))

    def test_staff_add_with_all_required_fields_succeeds(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New',
            'last_name': 'Rider',
            'email': 'newrider@example.com',
            'phone': '+16135550200',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'ride_leader_preference': 'n',
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '6135551234',
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.state, Registration.STATE_CONFIRMED)
        self.assertEqual(reg.emergency_contact_name, 'Emergency Contact')
