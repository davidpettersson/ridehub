import beartype.roar
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Ride, SpeedRange, Program, Route
from web.forms import RegistrationForm, EmailLoginForm


class RegistrationFormTest(TestCase):
    def setUp(self):
        now = timezone.now()
        program = Program.objects.create(name="Test Program")

        self.event_with_rides = Event.objects.create(
            name="Event with rides",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        # Create a route for the rides
        self.route = Route.objects.create(
            name="Test Route"
        )

        # Create a ride for the event
        Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride",
            route=self.route
        )

        self.event_without_rides = Event.objects.create(
            name="Event without rides",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        self.event_with_emergency_contact = Event.objects.create(
            name="Event with emergency contact",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=True,
            ride_leaders_wanted=False,
            requires_membership=False
        )

        self.event_with_ride_leader_preference = Event.objects.create(
            name="Event with ride leader preference",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=False,
            ride_leaders_wanted=True,
            requires_membership=False
        )

        self.event_with_membership_required = Event.objects.create(
            name="Event with membership required",
            program=program,
            starts_at=now,
            ends_at=now,
            registration_closes_at=now,
            requires_emergency_contact=False,
            ride_leaders_wanted=False,
            requires_membership=True
        )

        SpeedRange.objects.create(lower_limit=10, upper_limit=12)

    def test_form_raises_error_without_event(self):
        # Arrange, Act & Assert
        with self.assertRaises(beartype.roar.BeartypeDoorHintViolation):
            RegistrationForm(data={})

    def test_form_has_ride_and_speed_fields_when_event_has_rides(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_rides)

        # Assert
        self.assertIn("ride", form.fields)
        self.assertIn("speed_range_preference", form.fields)

    def test_form_does_not_have_ride_and_speed_fields_when_event_has_no_rides(self):
        # Arrange
        form = RegistrationForm(event=self.event_without_rides)

        # Assert
        self.assertNotIn("ride", form.fields)
        self.assertNotIn("speed_range_preference", form.fields)

    def test_form_has_emergency_contact_fields(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_emergency_contact)

        # Assert
        self.assertIn("emergency_contact_name", form.fields)
        self.assertIn("emergency_contact_phone", form.fields)

    def test_form_does_not_have_emergency_contact_fields(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_rides)

        # Assert
        self.assertNotIn("emergency_contact_name", form.fields)
        self.assertNotIn("emergency_contact_phone", form.fields)

    def test_form_has_ride_leader_preference(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_ride_leader_preference)

        # Assert
        self.assertIn("ride_leader_preference", form.fields)

    def test_form_does_not_have_ride_leader_preference(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_rides)

        # Assert
        self.assertNotIn("ride_leader_preference", form.fields)

    def test_form_has_membership_confirmation_when_required(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_membership_required)

        # Assert
        self.assertIn("membership_confirmation", form.fields)

    def test_form_does_not_have_membership_confirmation_when_not_required(self):
        # Arrange
        form = RegistrationForm(event=self.event_with_rides)

        # Assert
        self.assertNotIn("membership_confirmation", form.fields)

    def test_form_validation_fails_when_membership_confirmation_not_checked(self):
        # Arrange
        ride = Ride.objects.create(
            event=self.event_with_membership_required,
            name="Test Ride",
            route=self.route
        )
        speed_range = SpeedRange.objects.first()
        ride.speed_ranges.add(speed_range)  # Add speed range to ride
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            'speed_range_preference': speed_range.id,
            # membership_confirmation intentionally omitted
        }
        form = RegistrationForm(data=form_data, event=self.event_with_membership_required)

        # Act & Assert
        self.assertFalse(form.is_valid())
        self.assertIn('membership_confirmation', form.errors)
        self.assertEqual(
            form.errors['membership_confirmation'][0],
            'You must confirm that you are a current OBC member to register for this event.'
        )

    def test_form_validation_succeeds_when_membership_confirmation_checked(self):
        # Arrange
        ride = Ride.objects.create(
            event=self.event_with_membership_required,
            name="Test Ride",
            route=self.route
        )
        speed_range = SpeedRange.objects.first()
        ride.speed_ranges.add(speed_range)  # Add speed range to ride
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            'speed_range_preference': speed_range.id,
            'membership_confirmation': True
        }
        form = RegistrationForm(data=form_data, event=self.event_with_membership_required)

        # Act & Assert
        self.assertTrue(form.is_valid())

    def test_form_has_phone_field(self):
        # Arrange
        form = RegistrationForm(event=self.event_without_rides)

        # Assert
        self.assertIn("phone", form.fields)
        self.assertTrue(form.fields["phone"].required)

    def test_form_validation_fails_without_phone(self):
        # Arrange
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            # phone intentionally omitted
        }
        form = RegistrationForm(data=form_data, event=self.event_without_rides)

        # Act & Assert
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_form_validation_succeeds_with_phone(self):
        # Arrange
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
        }
        form = RegistrationForm(data=form_data, event=self.event_without_rides)

        # Act & Assert
        self.assertTrue(form.is_valid())

    def test_form_validation_succeeds_with_ride_without_speed_ranges(self):
        # Arrange
        # Create a ride without speed ranges
        ride = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride No Speed",
            route=self.route
        )
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            # No speed range preference - should be valid
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertTrue(form.is_valid())

    def test_form_validation_succeeds_with_ride_with_speed_ranges_and_valid_selection(self):
        # Arrange
        # Create a ride with speed ranges
        ride = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride With Speed",
            route=self.route
        )
        speed_range = SpeedRange.objects.create(lower_limit=15, upper_limit=18)
        ride.speed_ranges.add(speed_range)
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            'speed_range_preference': speed_range.id,
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertTrue(form.is_valid())

    def test_form_validation_fails_with_ride_with_speed_ranges_and_no_selection(self):
        # Arrange
        # Create a ride with speed ranges
        ride = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride With Speed",
            route=self.route
        )
        speed_range = SpeedRange.objects.create(lower_limit=15, upper_limit=18)
        ride.speed_ranges.add(speed_range)
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            # No speed range preference - should be invalid since ride has speed ranges
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertFalse(form.is_valid())
        self.assertIn('speed_range_preference', form.errors)
        self.assertEqual(
            form.errors['speed_range_preference'][0],
            'A speed range selection is required for this ride.'
        )

    def test_form_validation_fails_with_speed_range_not_for_selected_ride(self):
        # Arrange
        # Create two rides with different speed ranges
        ride1 = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride 1",
            route=self.route
        )
        ride2 = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride 2",
            route=self.route
        )
        
        speed_range1 = SpeedRange.objects.create(lower_limit=15, upper_limit=18)
        speed_range2 = SpeedRange.objects.create(lower_limit=20, upper_limit=23)
        
        ride1.speed_ranges.add(speed_range1)
        ride2.speed_ranges.add(speed_range2)
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride1.id,
            'speed_range_preference': speed_range2.id,  # Speed range belongs to ride2, not ride1
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertFalse(form.is_valid())
        self.assertIn('speed_range_preference', form.errors)
        self.assertEqual(
            form.errors['speed_range_preference'][0],
            'Selected speed range is not available for this ride.'
        )

    def test_form_validation_succeeds_with_multiple_speed_ranges_available(self):
        # Arrange
        # Create a ride with multiple speed ranges
        ride = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride Multiple Speed",
            route=self.route
        )
        speed_range1 = SpeedRange.objects.create(lower_limit=15, upper_limit=18)
        speed_range2 = SpeedRange.objects.create(lower_limit=20, upper_limit=23)
        ride.speed_ranges.add(speed_range1, speed_range2)
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            'speed_range_preference': speed_range2.id,  # Select the second speed range
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertTrue(form.is_valid())

    def test_form_validation_with_empty_string_speed_range_preference(self):
        # Arrange
        # Create a ride with speed ranges
        ride = Ride.objects.create(
            event=self.event_with_rides,
            name="Test Ride With Speed",
            route=self.route
        )
        speed_range = SpeedRange.objects.create(lower_limit=15, upper_limit=18)
        ride.speed_ranges.add(speed_range)
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'ride': ride.id,
            'speed_range_preference': '',  # Empty string should be treated as no selection
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertFalse(form.is_valid())
        self.assertIn('speed_range_preference', form.errors)
        self.assertEqual(
            form.errors['speed_range_preference'][0],
            'A speed range selection is required for this ride.'
        )

    def test_form_validation_without_ride_selected(self):
        # Arrange
        # Test the case where no ride is selected - speed range should not be required
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            # No ride selected
        }
        form = RegistrationForm(data=form_data, event=self.event_with_rides)

        # Act & Assert
        self.assertFalse(form.is_valid())  # Should fail because ride is required
        self.assertIn('ride', form.errors)
        # But speed_range_preference should not have errors since no ride is selected
        self.assertNotIn('speed_range_preference', form.errors)


class EmailLoginFormTest(TestCase):
    def test_form_has_email_field(self):
        # Arrange
        form = EmailLoginForm()

        # Assert
        self.assertIn("email", form.fields)
