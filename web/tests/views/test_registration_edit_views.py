from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
from backoffice.models import (
    Event, Program, Registration, RegistrationAmendment, Ride, Route, SpeedRange,
)


class BaseRegistrationEditViewTestCase(TestCase):
    def setUp(self):
        # Arrange
        self.now = timezone.now()
        self.program = Program.objects.create(name="Test Program")

        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=self.now + timezone.timedelta(days=7),
            ends_at=self.now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=self.now + timezone.timedelta(days=6),
            requires_emergency_contact=True,
            ride_leaders_wanted=True,
        )

        self.route = Route.objects.create(name="Test Route")
        self.ride = Ride.objects.create(event=self.event, route=self.route, ordering=1)
        self.other_ride = Ride.objects.create(event=self.event, route=self.route, ordering=2)

        self.speed_range = SpeedRange.objects.create(lower_limit=25, upper_limit=30)
        self.ride.speed_ranges.add(self.speed_range)
        self.other_ride.speed_ranges.add(self.speed_range)

        self.user = User.objects.create_user(
            username='rider@example.com',
            email='rider@example.com',
            password='password123',
            first_name='Rider',
            last_name='Person',
        )

        self.other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='password123',
        )

        self.registration = self._create_confirmed_registration(self.user)
        self.url = reverse('registration_edit', args=[self.registration.id])

    def _create_confirmed_registration(self, user, event=None) -> Registration:
        registration = Registration.objects.create(
            event=event or self.event,
            user=user,
            name=f'{user.first_name} {user.last_name}',
            first_name=user.first_name or 'Rider',
            last_name=user.last_name or 'Person',
            email=user.email,
            phone='+16135550100',
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            emergency_contact_name='Original Contact',
            emergency_contact_phone='+16135550111',
        )
        registration.confirm()
        registration.save()
        return registration

    def _reload(self, registration=None) -> Registration:
        return Registration.objects.get(id=(registration or self.registration).id)

    def _post_data(self, **overrides) -> dict:
        data = {
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'emergency_contact_name': 'Original Contact',
            'emergency_contact_phone': '+16135550111',
        }
        data.update(overrides)
        return data

    def _login(self):
        self.client.login(username='rider@example.com', password='password123')


class RegistrationEditAccessTests(BaseRegistrationEditViewTestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(302, response.status_code)
        self.assertIn('/login', response.url)

    def test_other_user_cannot_edit_the_registration(self):
        # Arrange
        self.client.login(username='other@example.com', password='password123')

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(404, response.status_code)

    def test_owner_can_open_the_edit_page(self):
        # Arrange
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'web/registrations/edit.html')

    def test_edit_page_shows_personal_details_as_read_only(self):
        # Arrange
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertNotIn('first_name', response.context['form'].fields)
        self.assertNotIn('last_name', response.context['form'].fields)
        self.assertNotIn('email', response.context['form'].fields)
        self.assertNotIn('phone', response.context['form'].fields)
        self.assertContains(response, 'rider@example.com')

    def test_edit_page_has_no_membership_confirmation(self):
        # Arrange
        self.event.requires_membership = True
        self.event.save()
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertNotIn('membership_confirmation', response.context['form'].fields)

    def test_started_event_redirects_to_profile(self):
        # Arrange
        self.event.starts_at = self.now - timezone.timedelta(minutes=5)
        self.event.ends_at = self.now + timezone.timedelta(hours=2)
        self.event.save()
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertRedirects(response, reverse('profile'))

    def test_started_event_rejects_a_post(self):
        # Arrange
        self.event.starts_at = self.now - timezone.timedelta(minutes=5)
        self.event.ends_at = self.now + timezone.timedelta(hours=2)
        self.event.save()
        self._login()

        # Act
        response = self.client.post(self.url, self._post_data(ride=self.other_ride.id))

        # Assert
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(self.ride, self._reload().ride)

    def test_cancelled_event_redirects_to_profile(self):
        # Arrange
        self.event.state = Event.STATE_CANCELLED
        self.event.save()
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertRedirects(response, reverse('profile'))

    def test_withdrawn_registration_redirects_to_profile(self):
        # Arrange
        self.registration.withdraw()
        self.registration.save()
        self._login()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertRedirects(response, reverse('profile'))


class RegistrationEditSubmissionTests(BaseRegistrationEditViewTestCase):
    def test_post_updates_the_registration(self):
        # Arrange
        self._login()

        # Act
        response = self.client.post(self.url, self._post_data(ride=self.other_ride.id))

        # Assert
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(self.other_ride, self._reload().ride)

    def test_post_sends_no_email(self):
        # Arrange
        self._login()

        # Act
        self.client.post(self.url, self._post_data(ride=self.other_ride.id))

        # Assert
        self.assertEqual(0, len(mail.outbox))

    def test_post_records_an_amendment_and_audit_event(self):
        # Arrange
        self._login()

        # Act
        self.client.post(self.url, self._post_data(ride=self.other_ride.id))

        # Assert
        amendment = RegistrationAmendment.objects.get(registration=self.registration)
        self.assertEqual(self.ride, amendment.ride)
        self.assertEqual(1, AuditEvent.objects.filter(action='registration_edited').count())

    def test_post_can_change_emergency_contact(self):
        # Arrange
        self._login()

        # Act
        self.client.post(self.url, self._post_data(
            emergency_contact_name='New Contact',
            emergency_contact_phone='+16135550222',
        ))

        # Assert
        registration = self._reload()
        self.assertEqual('New Contact', registration.emergency_contact_name)
        self.assertEqual('+16135550222', registration.emergency_contact_phone)

    def test_post_can_change_ride_leader_preference(self):
        # Arrange
        self._login()

        # Act
        self.client.post(self.url, self._post_data(ride_leader_preference='on'))

        # Assert
        self.assertEqual(
            Registration.RideLeaderPreference.YES, self._reload().ride_leader_preference
        )

    def test_post_keeps_the_registration_and_its_state(self):
        # Arrange
        self._login()

        # Act
        self.client.post(self.url, self._post_data(ride=self.other_ride.id))

        # Assert
        registration = self._reload()
        self.assertEqual(self.registration.id, registration.id)
        self.assertEqual(Registration.STATE_CONFIRMED, registration.state)
        self.assertEqual(1, Registration.objects.filter(event=self.event, user=self.user).count())

    def test_invalid_post_redisplays_the_form(self):
        # Arrange
        self._login()

        # Act
        response = self.client.post(self.url, self._post_data(emergency_contact_name=''))

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual('Original Contact', self._reload().emergency_contact_name)

    def test_unchanged_post_records_nothing(self):
        # Arrange
        self._login()

        # Act
        response = self.client.post(self.url, self._post_data())

        # Assert
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(0, RegistrationAmendment.objects.count())
        self.assertEqual(0, AuditEvent.objects.filter(action='registration_edited').count())

    def test_next_parameter_returns_to_the_event_page(self):
        # Arrange
        self._login()
        event_url = reverse('event_detail', args=[self.event.id])

        # Act
        response = self.client.post(
            f'{self.url}?next={event_url}', self._post_data(ride=self.other_ride.id)
        )

        # Assert
        self.assertRedirects(response, event_url)

    def test_external_next_parameter_is_ignored(self):
        # Arrange
        self._login()

        # Act
        response = self.client.post(
            f'{self.url}?next=https://evil.example.com/', self._post_data(ride=self.other_ride.id)
        )

        # Assert
        self.assertRedirects(response, reverse('profile'))


class RegistrationEditEntryPointTests(BaseRegistrationEditViewTestCase):
    def test_profile_page_offers_editing(self):
        # Arrange
        self._login()

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertContains(response, self.url)

    def test_profile_page_hides_editing_once_the_event_started(self):
        # Arrange
        self.event.starts_at = self.now - timezone.timedelta(minutes=5)
        self.event.ends_at = self.now + timezone.timedelta(hours=2)
        self.event.save()
        self._login()

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertNotContains(response, self.url)

    def test_event_page_offers_editing(self):
        # Arrange
        self._login()

        # Act
        response = self.client.get(reverse('event_detail', args=[self.event.id]))

        # Assert
        self.assertContains(response, self.url)
        self.assertTrue(response.context['user_registration'].editable)

    def test_event_page_hides_editing_for_events_without_editable_fields(self):
        # Arrange
        plain_event = Event.objects.create(
            name="Plain Event",
            program=self.program,
            starts_at=self.now + timezone.timedelta(days=3),
            registration_closes_at=self.now + timezone.timedelta(days=2),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
        )
        registration = Registration.objects.create(
            event=plain_event,
            user=self.user,
            name='Rider Person',
            first_name='Rider',
            last_name='Person',
            email=self.user.email,
            phone='+16135550100',
        )
        registration.confirm()
        registration.save()
        self._login()

        # Act
        response = self.client.get(reverse('event_detail', args=[plain_event.id]))

        # Assert
        self.assertNotContains(response, reverse('registration_edit', args=[registration.id]))
        self.assertFalse(response.context['user_registration'].editable)

    def test_event_page_for_anonymous_visitor_has_no_registration(self):
        # Act
        response = self.client.get(reverse('event_detail', args=[self.event.id]))

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.context['user_registration'])
