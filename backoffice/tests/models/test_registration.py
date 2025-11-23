from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from backoffice.models import Event, Registration, Program, Ride, Route, SpeedRange


class RegistrationCleanTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        self.route = Route.objects.create(name="Test Route")
        self.user = User.objects.create_user(username='testuser', email='test@example.com')
        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6)
        )

    def test_clean_passes_with_valid_data(self):
        registration = Registration(
            user=self.user,
            event=self.event,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )

        registration.clean()

    def test_clean_raises_error_when_ride_belongs_to_wrong_event(self):
        other_event = Event.objects.create(
            program=self.program,
            name="Other Event",
            starts_at=timezone.now() + timezone.timedelta(days=14),
            registration_closes_at=timezone.now() + timezone.timedelta(days=13)
        )
        ride = Ride.objects.create(name="Other Ride", event=other_event, route=self.route)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )

        with self.assertRaises(ValidationError) as context:
            registration.clean()

        self.assertIn('ride', context.exception.message_dict)

    def test_clean_raises_error_when_speed_range_not_available_for_ride(self):
        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)
        speed_range = SpeedRange.objects.create(lower_limit=20, upper_limit=25)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            speed_range_preference=speed_range,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )

        with self.assertRaises(ValidationError) as context:
            registration.clean()

        self.assertIn('speed_range_preference', context.exception.message_dict)

    def test_clean_passes_when_speed_range_available_for_ride(self):
        self.event.requires_emergency_contact = False
        self.event.save()

        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)
        speed_range = SpeedRange.objects.create(lower_limit=20, upper_limit=25)
        ride.speed_ranges.add(speed_range)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            speed_range_preference=speed_range,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            ride_leader_preference=Registration.RideLeaderPreference.NO
        )

        registration.clean()

    def test_clean_raises_error_when_emergency_contact_missing_but_required(self):
        self.event.requires_emergency_contact = True
        self.event.save()

        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )

        with self.assertRaises(ValidationError) as context:
            registration.clean()

        self.assertIn('emergency_contact_name', context.exception.message_dict)
        self.assertIn('emergency_contact_phone', context.exception.message_dict)

    def test_clean_passes_when_emergency_contact_provided(self):
        self.event.requires_emergency_contact = True
        self.event.save()

        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            emergency_contact_name="Emergency Contact",
            emergency_contact_phone="555-1234",
            ride_leader_preference=Registration.RideLeaderPreference.NO
        )

        registration.clean()

    def test_clean_raises_error_when_ride_leader_preference_missing_but_required(self):
        self.event.ride_leaders_wanted = True
        self.event.requires_emergency_contact = False
        self.event.save()

        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            ride_leader_preference=Registration.RideLeaderPreference.NOT_APPLICABLE
        )

        with self.assertRaises(ValidationError) as context:
            registration.clean()

        self.assertIn('ride_leader_preference', context.exception.message_dict)

    def test_clean_passes_when_ride_leader_preference_provided(self):
        self.event.ride_leaders_wanted = True
        self.event.requires_emergency_contact = False
        self.event.save()

        ride = Ride.objects.create(name="Test Ride", event=self.event, route=self.route)

        registration = Registration(
            user=self.user,
            event=self.event,
            ride=ride,
            name="Test User",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )

        registration.clean()
