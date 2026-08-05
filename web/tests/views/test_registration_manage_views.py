from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
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


class ManagePageAvailabilityTests(BaseManageTestCase):
    def _make_event_old(self):
        self.event.starts_at = timezone.now() - timezone.timedelta(hours=80)
        self.event.ends_at = timezone.now() - timezone.timedelta(hours=78)
        self.event.registration_closes_at = timezone.now() - timezone.timedelta(hours=81)
        self.event.save()

    def test_staff_can_view_manage_page_for_old_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)
        self._make_event_old()

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['registrations_available'])
        self.assertContains(response, 'Regular')

    def test_staff_can_access_add_form_for_old_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._make_event_old()

        # Act
        response = self.client.get(reverse('staff_registration_add', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_edit_form_for_old_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)
        self._make_event_old()

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 200)

    def test_staff_can_withdraw_registration_for_old_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)
        self._make_event_old()

        # Act
        response = self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        updated_reg = Registration.objects.get(id=reg.id)
        self.assertEqual(updated_reg.state, Registration.STATE_WITHDRAWN)


class ManagePageCopyEmailsTests(BaseManageTestCase):
    def test_manage_page_shows_copy_rider_emails_button(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertContains(response, 'Copy all rider emails')
        self.assertNotContains(response, 'Copy ride leader emails')
        self.assertFalse(response.context['has_ride_leaders'])

    def test_manage_page_shows_ride_leader_button_when_leaders_present(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.regular_user, self.ride, self.speed_range)
        reg.ride_leader_preference = Registration.RideLeaderPreference.YES
        reg.save()

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertContains(response, 'Copy ride leader emails')
        self.assertTrue(response.context['has_ride_leaders'])


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

    def test_manage_page_shows_confirmed_and_unverified_registrations(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(
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
        self.assertNotContains(response, 'Withdrawn')

    def test_manage_page_includes_unverified_registrations(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        unverified_user = User.objects.create_user(
            username='unverified@example.com', email='unverified@example.com',
            password='password123', first_name='Unverified', last_name='Person',
        )
        reg = Registration.objects.create(
            event=self.event,
            user=unverified_user,
            name='Unverified Person',
            first_name='Unverified',
            last_name='Person',
            email='unverified@example.com',
            ride=self.ride,
            speed_range_preference=self.speed_range,
        )
        reg.hold_for_verification()
        reg.save()

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unverified')


class ManagePageAuditTests(BaseManageTestCase):
    def _manage_url(self):
        return reverse('event_registrations_manage', args=[self.event.id])

    def test_staff_visit_logs_audit_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        self.client.get(self._manage_url())

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 1)
        audit_event = AuditEvent.objects.get()
        self.assertEqual(audit_event.action, 'registration_management_viewed')
        self.assertEqual(audit_event.actor, self.staff_user)
        self.assertEqual(audit_event.target, self.event)

    def test_each_visit_logs_a_separate_audit_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        self.client.get(self._manage_url())
        self.client.get(self._manage_url())

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_non_staff_denied_logs_no_audit_event(self):
        # Arrange
        self.client.login(username='regular@example.com', password='password123')

        # Act
        self.client.get(self._manage_url())

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_anonymous_visit_logs_no_audit_event(self):
        # Act
        self.client.get(self._manage_url())

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_external_registration_redirect_logs_no_audit_event(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self.event.external_registration_url = 'https://example.com/register'
        self.event.save(update_fields=['external_registration_url'])

        # Act
        self.client.get(self._manage_url())

        # Assert
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_response_is_not_cacheable(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(self._manage_url())

        # Assert
        self.assertIn('no-store', response['Cache-Control'])


class ManagePageFilterAndSortRegressionTests(BaseManageTestCase):
    def test_manage_page_filter_card_present(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(
            self.staff_user, ride=self.ride, speed_range=self.speed_range,
        )

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="search"')
        self.assertContains(response, 'name="ride"')
        self.assertContains(response, 'name="ride_leader_preference"')

    def test_manage_page_sorting_still_works(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        self._create_confirmed_registration(
            self.staff_user, ride=self.ride, speed_range=self.speed_range,
        )
        self._create_confirmed_registration(
            self.regular_user, ride=self.ride, speed_range=self.speed_range,
        )

        # Act
        response = self.client.get(
            reverse('event_registrations_manage', args=[self.event.id]),
            {'sort': 'name'},
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        rows = list(table.rows)
        names = [str(row.get_cell('name')) for row in rows]
        self.assertEqual(len(names), 2)
        self.assertIn('Regular', names[0])
        self.assertIn('Staff', names[1])


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

    def test_staff_can_withdraw_unverified_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        unverified_user = User.objects.create_user(
            username='unverified@example.com', email='unverified@example.com',
            password='password123', first_name='Unverified', last_name='User',
        )
        reg = Registration.objects.create(
            event=self.event,
            user=unverified_user,
            name='Unverified User',
            first_name='Unverified',
            last_name='User',
            email='unverified@example.com',
            phone='+16135550100',
            ride=self.ride,
            speed_range_preference=self.speed_range,
        )
        reg.hold_for_verification()
        reg.save()

        # Act
        from django.core import mail
        response = self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(id=reg.id)
        self.assertEqual(reg.state, Registration.STATE_WITHDRAWN)
        self.assertEqual(len(mail.outbox), 0)

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

    def test_staff_add_without_ride_leader_checkbox_checked_stores_no(self):
        # Arrange: ride_leader_preference is now a checkbox; omitting it means unchecked (NO), which is valid
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
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.ride_leader_preference, Registration.RideLeaderPreference.NO)

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


class StaffFirstTimeAttendeeTests(TestCase):
    def setUp(self):
        # Arrange
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Event with first-time question",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            ends_at=now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False,
            ask_first_time_attendee=True,
        )
        self.route = Route.objects.create(name="Test Route")
        self.ride = Ride.objects.create(event=self.event, route=self.route, ordering=1)
        self.staff_user = User.objects.create_user(
            username='staff@example.com', email='staff@example.com',
            password='password123', is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular@example.com', email='regular@example.com',
            password='password123', first_name='Reg', last_name='User',
        )

    def _create_registration(self, first_time_value):
        reg = Registration.objects.create(
            event=self.event,
            user=self.regular_user,
            name=self.regular_user.get_full_name(),
            first_name=self.regular_user.first_name,
            last_name=self.regular_user.last_name,
            email=self.regular_user.email,
            phone='+16135550100',
            ride=self.ride,
            first_time_attendee=first_time_value,
        )
        reg.confirm()
        reg.save()
        return reg

    def test_staff_add_persists_first_time_attendee_yes_when_checked(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New', 'last_name': 'Rider',
            'email': 'newrider@example.com', 'phone': '+16135550200',
            'ride': self.ride.id,
            'first_time_attendee': 'on',
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.first_time_attendee, Registration.FirstTimeAttendee.YES)

    def test_staff_add_persists_first_time_attendee_no_when_unchecked(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New', 'last_name': 'Rider',
            'email': 'newrider@example.com', 'phone': '+16135550200',
            'ride': self.ride.id,
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.first_time_attendee, Registration.FirstTimeAttendee.NO)

    def test_staff_edit_resolves_legacy_not_applicable_to_no_when_unchecked(self):
        # Arrange: legacy registration (NOT_APPLICABLE on an event that now asks the question).
        # Editing without checking the box resolves it to NO, matching the form's displayed state.
        reg = self._create_registration(Registration.FirstTimeAttendee.NOT_APPLICABLE)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(
            reverse('staff_registration_edit', args=[self.event.id, reg.id]),
            {
                'first_name': reg.first_name, 'last_name': reg.last_name,
                'email': reg.email, 'phone': reg.phone,
                'ride': self.ride.id,
            },
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reloaded = Registration.objects.get(id=reg.id)
        self.assertEqual(reloaded.first_time_attendee, Registration.FirstTimeAttendee.NO)

    def test_staff_edit_writes_yes_when_checkbox_checked(self):
        # Arrange
        reg = self._create_registration(Registration.FirstTimeAttendee.NO)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(
            reverse('staff_registration_edit', args=[self.event.id, reg.id]),
            {
                'first_name': reg.first_name, 'last_name': reg.last_name,
                'email': reg.email, 'phone': reg.phone,
                'ride': self.ride.id,
                'first_time_attendee': 'on',
            },
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reloaded = Registration.objects.get(id=reg.id)
        self.assertEqual(reloaded.first_time_attendee, Registration.FirstTimeAttendee.YES)

    def test_first_time_column_visible_on_manage_when_event_asks(self):
        # Arrange
        self._create_registration(Registration.FirstTimeAttendee.YES)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        column_names = [col.name for col in table.columns]
        self.assertIn('first_time_attendee', column_names)

    def test_first_time_column_hidden_on_manage_when_event_does_not_ask(self):
        # Arrange
        self.event.ask_first_time_attendee = False
        self.event.save(update_fields=['ask_first_time_attendee'])
        self._create_registration(Registration.FirstTimeAttendee.NOT_APPLICABLE)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        column_names = [col.name for col in table.columns]
        self.assertNotIn('first_time_attendee', column_names)


class StaffProspectiveMemberTests(TestCase):
    def setUp(self):
        # Arrange
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Event with prospective member question",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            ends_at=now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=now + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False,
            ask_prospective_member=True,
        )
        self.route = Route.objects.create(name="Test Route")
        self.ride = Ride.objects.create(event=self.event, route=self.route, ordering=1)
        self.staff_user = User.objects.create_user(
            username='staff@example.com', email='staff@example.com',
            password='password123', is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular@example.com', email='regular@example.com',
            password='password123', first_name='Reg', last_name='User',
        )

    def _create_registration(self, prospective_member_value):
        reg = Registration.objects.create(
            event=self.event,
            user=self.regular_user,
            name=self.regular_user.get_full_name(),
            first_name=self.regular_user.first_name,
            last_name=self.regular_user.last_name,
            email=self.regular_user.email,
            phone='+16135550100',
            ride=self.ride,
            prospective_member=prospective_member_value,
        )
        reg.confirm()
        reg.save()
        return reg

    def _column_names(self):
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))
        self.assertEqual(response.status_code, 200)
        return [col.name for col in response.context['table'].columns]

    def test_staff_add_persists_prospective_member_yes_when_checked(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New', 'last_name': 'Rider',
            'email': 'newrider@example.com', 'phone': '+16135550200',
            'ride': self.ride.id,
            'prospective_member': 'on',
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.prospective_member, Registration.ProspectiveMember.YES)

    def test_staff_add_persists_prospective_member_no_when_unchecked(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(reverse('staff_registration_add', args=[self.event.id]), {
            'first_name': 'New', 'last_name': 'Rider',
            'email': 'newrider@example.com', 'phone': '+16135550200',
            'ride': self.ride.id,
        })

        # Assert
        self.assertEqual(response.status_code, 302)
        reg = Registration.objects.get(email='newrider@example.com')
        self.assertEqual(reg.prospective_member, Registration.ProspectiveMember.NO)

    def test_staff_edit_writes_yes_when_checkbox_checked(self):
        # Arrange
        reg = self._create_registration(Registration.ProspectiveMember.NO)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.post(
            reverse('staff_registration_edit', args=[self.event.id, reg.id]),
            {
                'first_name': reg.first_name, 'last_name': reg.last_name,
                'email': reg.email, 'phone': reg.phone,
                'ride': self.ride.id,
                'prospective_member': 'on',
            },
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        reloaded = Registration.objects.get(id=reg.id)
        self.assertEqual(reloaded.prospective_member, Registration.ProspectiveMember.YES)

    def test_staff_edit_form_is_prefilled_from_the_registration(self):
        # Arrange
        reg = self._create_registration(Registration.ProspectiveMember.YES)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].initial['prospective_member'])

    def test_prospective_member_column_visible_on_manage_when_event_asks(self):
        # Arrange
        self._create_registration(Registration.ProspectiveMember.YES)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        column_names = self._column_names()

        # Assert
        self.assertIn('prospective_member', column_names)

    def test_prospective_member_column_hidden_on_manage_when_event_does_not_ask(self):
        # Arrange
        self.event.ask_prospective_member = False
        self.event.save(update_fields=['ask_prospective_member'])
        self._create_registration(Registration.ProspectiveMember.NOT_APPLICABLE)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        column_names = self._column_names()

        # Assert
        self.assertNotIn('prospective_member', column_names)

    def test_both_question_columns_visible_when_event_asks_both(self):
        # Arrange
        self.event.ask_first_time_attendee = True
        self.event.save(update_fields=['ask_first_time_attendee'])
        reg = self._create_registration(Registration.ProspectiveMember.YES)
        reg.first_time_attendee = Registration.FirstTimeAttendee.YES
        reg.save(update_fields=['first_time_attendee'])
        self.client.login(username='staff@example.com', password='password123')

        # Act
        column_names = self._column_names()

        # Assert
        self.assertIn('prospective_member', column_names)
        self.assertIn('first_time_attendee', column_names)

    def test_neither_question_column_visible_when_event_asks_neither(self):
        # Arrange
        self.event.ask_prospective_member = False
        self.event.ask_first_time_attendee = False
        self.event.save(update_fields=['ask_prospective_member', 'ask_first_time_attendee'])
        self._create_registration(Registration.ProspectiveMember.NOT_APPLICABLE)
        self.client.login(username='staff@example.com', password='password123')

        # Act
        column_names = self._column_names()

        # Assert
        self.assertNotIn('prospective_member', column_names)
        self.assertNotIn('first_time_attendee', column_names)


class ExternalRegistrationBlocksManageTests(BaseManageTestCase):
    def setUp(self):
        super().setUp()
        self.event.external_registration_url = 'https://example.com/register'
        self.event.save(update_fields=['external_registration_url'])

    def _event_detail_url(self):
        return reverse('event_detail', args=[self.event.id])

    def test_manage_page_redirects_for_external_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('event_registrations_manage', args=[self.event.id]))

        # Assert
        self.assertRedirects(response, self._event_detail_url())

    def test_add_redirects_for_external_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')

        # Act
        response = self.client.get(reverse('staff_registration_add', args=[self.event.id]))

        # Assert
        self.assertRedirects(response, self._event_detail_url())

    def test_edit_redirects_for_external_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.staff_user, self.ride, self.speed_range)

        # Act
        response = self.client.get(
            reverse('staff_registration_edit', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertRedirects(response, self._event_detail_url())

    def test_withdraw_redirects_for_external_registration(self):
        # Arrange
        self.client.login(username='staff@example.com', password='password123')
        reg = self._create_confirmed_registration(self.staff_user, self.ride, self.speed_range)

        # Act
        response = self.client.post(
            reverse('staff_registration_withdraw', args=[self.event.id, reg.id])
        )

        # Assert
        self.assertRedirects(response, self._event_detail_url())
        updated_reg = Registration.objects.get(id=reg.id)
        self.assertEqual(updated_reg.state, Registration.STATE_CONFIRMED)
