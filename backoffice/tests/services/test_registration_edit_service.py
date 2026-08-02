from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from audit.models import AuditEvent
from backoffice.models import (
    Event, Program, Registration, RegistrationSnapshot, Ride, Route, SpeedRange,
)
from backoffice.services.registration_service import RegistrationDetail, RegistrationService


class BaseRegistrationEditTestCase(TestCase):
    def setUp(self):
        # Arrange
        self.service = RegistrationService()
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
        self.faster_speed_range = SpeedRange.objects.create(lower_limit=30, upper_limit=35)
        self.ride.speed_ranges.add(self.speed_range, self.faster_speed_range)
        self.other_ride.speed_ranges.add(self.speed_range)

        self.user = User.objects.create_user(
            username='rider@example.com',
            email='rider@example.com',
            password='password123',
            first_name='Rider',
            last_name='Person',
        )

        self.staff_user = User.objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password='password123',
            is_staff=True,
        )

        self.registration = self._create_confirmed_registration()

    def _create_confirmed_registration(self, event=None) -> Registration:
        registration = Registration.objects.create(
            event=event or self.event,
            user=self.user,
            name='Rider Person',
            first_name='Rider',
            last_name='Person',
            email=self.user.email,
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

    def _detail(self, **overrides) -> RegistrationDetail:
        values = {
            'ride': self.ride,
            'speed_range_preference': self.speed_range,
            'ride_leader_preference': Registration.RideLeaderPreference.NO,
            'emergency_contact_name': 'Original Contact',
            'emergency_contact_phone': '+16135550111',
            'first_time_attendee': None,
        }
        values.update(overrides)
        return RegistrationDetail(**values)


class EditRegistrationTests(BaseRegistrationEditTestCase):
    def test_edit_applies_changes(self):
        # Act
        changed = self.service.edit_registration(
            self.registration, self.user,
            self._detail(ride=self.other_ride, speed_range_preference=self.speed_range),
        )

        # Assert
        self.registration = self._reload()
        self.assertTrue(changed)
        self.assertEqual(self.other_ride, self.registration.ride)

    def test_edit_returns_only_the_fields_that_changed(self):
        # Act
        changed_fields = self.service.edit_registration(
            self.registration, self.user,
            self._detail(ride=self.other_ride, emergency_contact_name='New Contact'),
        )

        # Assert
        self.assertEqual({'ride', 'emergency_contact_name'}, set(changed_fields))

    def test_edit_without_changes_returns_no_fields(self):
        # Act
        changed_fields = self.service.edit_registration(
            self.registration, self.user, self._detail()
        )

        # Assert
        self.assertEqual([], changed_fields)

    def test_edit_keeps_the_same_registration(self):
        # Arrange
        registration_id = self.registration.id

        # Act
        self.service.edit_registration(
            self.registration, self.user, self._detail(ride=self.other_ride)
        )

        # Assert
        self.assertEqual(registration_id, self.registration.id)
        self.assertEqual(Registration.STATE_CONFIRMED, self.registration.state)
        self.assertEqual(1, Registration.objects.filter(event=self.event, user=self.user).count())

    def test_edit_does_not_change_personal_details(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user, self._detail(ride=self.other_ride)
        )

        # Assert
        self.registration = self._reload()
        self.assertEqual('Rider', self.registration.first_name)
        self.assertEqual('Person', self.registration.last_name)
        self.assertEqual('rider@example.com', self.registration.email)
        self.assertEqual('+16135550100', self.registration.phone)

    def test_edit_sends_no_email(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user, self._detail(ride=self.other_ride)
        )

        # Assert
        self.assertEqual(0, len(mail.outbox))

    def test_edit_logs_an_audit_event(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user, self._detail(ride=self.other_ride)
        )

        # Assert
        audit_event = AuditEvent.objects.get(action='registration_edited')
        self.assertEqual(self.user, audit_event.actor)
        self.assertEqual(self.registration, audit_event.target)

    def test_edit_records_previous_details(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user,
            self._detail(
                ride=self.other_ride,
                emergency_contact_name='New Contact',
                emergency_contact_phone='+16135550222',
            ),
        )

        # Assert
        snapshot = RegistrationSnapshot.objects.get(registration=self.registration)
        self.assertEqual(self.user, snapshot.actor)
        self.assertEqual(self.ride, snapshot.ride)
        self.assertEqual(self.speed_range, snapshot.speed_range_preference)
        self.assertEqual('Original Contact', snapshot.emergency_contact_name)
        self.assertEqual('+16135550111', snapshot.emergency_contact_phone)
        self.assertEqual('Rider', snapshot.first_name)
        self.assertEqual('rider@example.com', snapshot.email)

    def test_edit_records_which_fields_changed(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user,
            self._detail(ride=self.other_ride, emergency_contact_name='New Contact'),
        )

        # Assert
        snapshot = RegistrationSnapshot.objects.get(registration=self.registration)
        self.assertEqual({'ride', 'emergency_contact_name'}, set(snapshot.changed_fields))

    def test_repeated_edits_accumulate_snapshots(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user, self._detail(ride=self.other_ride)
        )
        self.service.edit_registration(
            self.registration, self.user,
            self._detail(ride=self.other_ride, emergency_contact_name='New Contact'),
        )

        # Assert
        snapshots = list(RegistrationSnapshot.objects.filter(registration=self.registration))
        self.assertEqual(2, len(snapshots))
        self.assertEqual(['emergency_contact_name'], snapshots[0].changed_fields)
        self.assertEqual(['ride'], snapshots[1].changed_fields)

    def test_edit_without_changes_records_nothing(self):
        # Act
        changed = self.service.edit_registration(self.registration, self.user, self._detail())

        # Assert
        self.assertFalse(changed)
        self.assertEqual(0, RegistrationSnapshot.objects.count())
        self.assertEqual(0, AuditEvent.objects.filter(action='registration_edited').count())

    def test_edit_can_change_ride_leader_preference(self):
        # Act
        self.service.edit_registration(
            self.registration, self.user,
            self._detail(ride_leader_preference=Registration.RideLeaderPreference.YES),
        )

        # Assert
        self.registration = self._reload()
        self.assertEqual(Registration.RideLeaderPreference.YES, self.registration.ride_leader_preference)

    def test_edit_can_change_first_time_attendee(self):
        # Arrange
        self.event.ask_first_time_attendee = True
        self.event.save()
        self.registration.first_time_attendee = Registration.FirstTimeAttendee.NO
        self.registration.save()

        # Act
        self.service.edit_registration(
            self.registration, self.user,
            self._detail(first_time_attendee=Registration.FirstTimeAttendee.YES),
        )

        # Assert
        self.registration = self._reload()
        self.assertEqual(Registration.FirstTimeAttendee.YES, self.registration.first_time_attendee)

    def test_edit_rejects_invalid_speed_range(self):
        # Act & Assert
        with self.assertRaises(ValidationError):
            self.service.edit_registration(
                self.registration, self.user,
                self._detail(ride=self.other_ride, speed_range_preference=self.faster_speed_range),
            )

    def test_edit_rolls_back_when_invalid(self):
        # Act
        with self.assertRaises(ValidationError):
            self.service.edit_registration(
                self.registration, self.user,
                self._detail(ride=self.other_ride, speed_range_preference=self.faster_speed_range),
            )

        # Assert
        self.registration = self._reload()
        self.assertEqual(self.ride, self.registration.ride)
        self.assertEqual(0, RegistrationSnapshot.objects.count())


class RegistrationEditabilityTests(BaseRegistrationEditTestCase):
    def test_confirmed_future_registration_is_editable(self):
        # Act
        allowed, reason = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_editable_after_registration_closes(self):
        # Arrange
        self.event.registration_closes_at = self.now - timezone.timedelta(days=1)
        self.event.save()

        # Act
        allowed, _ = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertTrue(allowed)

    def test_not_editable_once_event_has_started(self):
        # Arrange
        self.event.starts_at = self.now - timezone.timedelta(minutes=1)
        self.event.ends_at = self.now + timezone.timedelta(hours=2)
        self.event.save()
        self.registration = self._reload()

        # Act
        allowed, reason = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertFalse(allowed)
        self.assertEqual('Event has already started.', reason)

    def test_not_editable_when_event_is_cancelled(self):
        # Arrange
        self.event.state = Event.STATE_CANCELLED
        self.event.save()
        self.registration = self._reload()

        # Act
        allowed, reason = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertFalse(allowed)
        self.assertEqual('Event is cancelled.', reason)

    def test_not_editable_when_event_is_archived(self):
        # Arrange
        self.event.state = Event.STATE_ARCHIVED
        self.event.save()
        self.registration = self._reload()

        # Act
        allowed, reason = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertFalse(allowed)
        self.assertEqual('Event is archived.', reason)

    def test_not_editable_when_withdrawn(self):
        # Arrange
        self.registration.withdraw()
        self.registration.save()

        # Act
        allowed, reason = self.service.is_registration_editable(self.registration)

        # Assert
        self.assertFalse(allowed)
        self.assertEqual('Only confirmed registrations can be edited.', reason)

    def test_not_editable_when_event_has_no_editable_fields(self):
        # Arrange
        plain_event = Event.objects.create(
            name="Plain Event",
            program=self.program,
            starts_at=self.now + timezone.timedelta(days=3),
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            ask_first_time_attendee=False,
        )
        registration = self._create_confirmed_registration(event=plain_event)
        registration.ride = None
        registration.speed_range_preference = None
        registration.ride_leader_preference = Registration.RideLeaderPreference.NOT_APPLICABLE
        registration.save()

        # Act
        allowed, reason = self.service.is_registration_editable(registration)

        # Assert
        self.assertFalse(allowed)
        self.assertEqual('This event has no editable registration details.', reason)

    def test_edit_raises_when_not_allowed(self):
        # Arrange
        self.event.state = Event.STATE_CANCELLED
        self.event.save()
        self.registration = self._reload()

        # Act & Assert
        with self.assertRaises(ValueError):
            self.service.edit_registration(
                self.registration, self.user, self._detail(ride=self.other_ride)
            )

    def test_mark_editable_sets_the_attribute(self):
        # Act
        registrations = self.service.mark_editable([self.registration])

        # Assert
        self.assertTrue(registrations[0].editable)


class StaffUpdateSnapshotTests(BaseRegistrationEditTestCase):
    def test_staff_edit_records_previous_details(self):
        # Act
        self.service.staff_update_registration(
            self.registration, self.staff_user, first_name='Renamed', ride=self.other_ride
        )

        # Assert
        snapshot = RegistrationSnapshot.objects.get(registration=self.registration)
        self.assertEqual(self.staff_user, snapshot.actor)
        self.assertEqual('Rider', snapshot.first_name)
        self.assertEqual(self.ride, snapshot.ride)
        self.assertEqual({'first_name', 'ride'}, set(snapshot.changed_fields))

    def test_staff_edit_returns_only_the_fields_that_changed(self):
        # Act
        changed_fields = self.service.staff_update_registration(
            self.registration, self.staff_user, first_name='Renamed', ride=self.ride
        )

        # Assert
        self.assertEqual(['first_name'], changed_fields)

    def test_staff_edit_still_updates_the_registration(self):
        # Act
        changed = self.service.staff_update_registration(
            self.registration, self.staff_user, first_name='Renamed'
        )

        # Assert
        self.registration = self._reload()
        self.assertTrue(changed)
        self.assertEqual('Renamed', self.registration.first_name)
        self.assertEqual('Renamed Person', self.registration.name)
        self.assertEqual(1, AuditEvent.objects.filter(action='staff_edited').count())

    def test_staff_edit_without_changes_records_nothing(self):
        # Act
        changed = self.service.staff_update_registration(
            self.registration, self.staff_user, first_name='Rider', ride=self.ride
        )

        # Assert
        self.assertFalse(changed)
        self.assertEqual(0, RegistrationSnapshot.objects.count())
        self.assertEqual(0, AuditEvent.objects.filter(action='staff_edited').count())
