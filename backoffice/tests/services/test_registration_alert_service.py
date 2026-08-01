from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from backoffice.models import Event, Program, Registration
from backoffice.services.registration_alert_service import RegistrationAlertService


@override_settings(REGISTRATION_ALERT_EMAILS=['staff@example.com'])
class RegistrationAlertServiceTests(TestCase):

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        starts_at = timezone.now() + timedelta(days=7)
        self.event = Event.objects.create(
            name='Test Event',
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            program=self.program,
            location='Test Location',
            description='Test Description',
        )
        self.service = RegistrationAlertService()

    def _create_registration(self, state, submitted_ago, name='Stale Rider'):
        registration = Registration.objects.create(
            event=self.event,
            first_name=name.split()[0],
            last_name=name.split()[1],
            name=name,
            email='rider@example.com',
            ride_leader_preference=Registration.RideLeaderPreference.NO,
        )
        Registration.objects.filter(id=registration.id).update(
            state=state,
            submitted_at=timezone.now() - submitted_ago,
        )
        return Registration.objects.get(id=registration.id)

    def test_alerts_about_registration_unconfirmed_for_more_than_an_hour(self):
        # Arrange
        registration = self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['staff@example.com'])
        self.assertIn(registration.name, mail.outbox[0].body)

    def test_alerts_about_submitted_registrations(self):
        # Arrange
        self._create_registration(Registration.STATE_SUBMITTED, timedelta(hours=3))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_ignores_registration_unconfirmed_for_less_than_an_hour(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(minutes=30))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_confirmed_registration(self):
        # Arrange
        self._create_registration(Registration.STATE_CONFIRMED, timedelta(hours=2))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_withdrawn_registration(self):
        # Arrange
        self._create_registration(Registration.STATE_WITHDRAWN, timedelta(hours=2))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_alert_twice_about_the_same_registration(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))
        self.service.alert_unconfirmed_registrations()

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_records_when_the_alert_was_sent(self):
        # Arrange
        registration = self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))

        # Act
        self.service.alert_unconfirmed_registrations()

        # Assert
        registration = Registration.objects.get(id=registration.id)
        self.assertIsNotNone(registration.unconfirmed_alert_sent_at)

    def test_sends_a_single_digest_for_multiple_registrations(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2), name='First Rider')
        self._create_registration(Registration.STATE_SUBMITTED, timedelta(hours=4), name='Second Rider')

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('First Rider', mail.outbox[0].body)
        self.assertIn('Second Rider', mail.outbox[0].body)

    @override_settings(REGISTRATION_ALERT_EMAILS=[])
    def test_sends_nothing_when_no_recipients_configured(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)
