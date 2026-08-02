from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from backoffice.models import Event, Notification, Program, Registration
from backoffice.services.registration_alert_service import RegistrationAlertService


@override_settings(REGISTRATION_ALERT_EMAILS=['staff@example.com'])
class RegistrationAlertServiceTests(TestCase):

    def setUp(self):
        self.program = Program.objects.create(name='Test Program')
        self.event = self._create_event('Test Event', timezone.now() + timedelta(hours=24))
        self.service = RegistrationAlertService()

    def _create_event(self, name, starts_at):
        return Event.objects.create(
            name=name,
            starts_at=starts_at,
            registration_closes_at=starts_at - timedelta(hours=1),
            program=self.program,
            location='Test Location',
            description='Test Description',
        )

    def _create_registration(self, state, submitted_ago, name='Stale Rider', event=None):
        registration = Registration.objects.create(
            event=event or self.event,
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

    def test_alerts_again_while_the_registration_stays_unconfirmed(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))
        self.service.alert_unconfirmed_registrations()

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_stops_alerting_once_the_registration_is_confirmed(self):
        # Arrange
        registration = self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))
        self.service.alert_unconfirmed_registrations()
        registration.confirm()
        registration.save()

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 1)

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

    def test_ignores_registrations_for_past_events(self):
        # Arrange
        past_event = self._create_event('Past Event', timezone.now() - timedelta(hours=1))
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2), event=past_event)

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_registrations_for_events_more_than_48_hours_away(self):
        # Arrange
        distant_event = self._create_event('Distant Event', timezone.now() + timedelta(hours=49))
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2), event=distant_event)

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_alerts_about_registrations_for_events_within_48_hours(self):
        # Arrange
        soon_event = self._create_event('Soon Event', timezone.now() + timedelta(hours=47))
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2), event=soon_event)

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_orders_registrations_by_event_start_time(self):
        # Arrange
        later_event = self._create_event('Later Event', timezone.now() + timedelta(hours=40))
        earlier_event = self._create_event('Earlier Event', timezone.now() + timedelta(hours=4))
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2), name='Later Rider',
                                  event=later_event)
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=3), name='Earlier Rider',
                                  event=earlier_event)

        # Act
        self.service.alert_unconfirmed_registrations()

        # Assert
        body = mail.outbox[0].body
        self.assertLess(body.index('Earlier Rider'), body.index('Later Rider'))

    @override_settings(REGISTRATION_ALERT_EMAILS=[])
    def test_sends_nothing_when_no_recipients_configured(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))

        # Act
        alerted = self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(alerted, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_records_a_notification_for_the_digest(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))

        # Act
        self.service.alert_unconfirmed_registrations()

        # Assert
        notification = Notification.objects.get()
        self.assertEqual(notification.kind, Notification.KIND_STAFF_UNCONFIRMED_DIGEST)
        self.assertEqual(notification.recipients, ['staff@example.com'])
        self.assertIsNone(notification.target)

    def test_records_a_notification_for_every_digest_sent(self):
        # Arrange
        self._create_registration(Registration.STATE_UNVERIFIED, timedelta(hours=2))
        self.service.alert_unconfirmed_registrations()

        # Act
        self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(Notification.objects.count(), 2)

    def test_records_nothing_when_there_is_nothing_to_alert_about(self):
        # Act
        self.service.alert_unconfirmed_registrations()

        # Assert
        self.assertEqual(Notification.objects.count(), 0)
