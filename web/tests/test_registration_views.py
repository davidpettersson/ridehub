from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Program, Event, Registration, Ride, SpeedRange


class RegistrationViewsTestCase(TestCase):
    def setUp(self):
        # Set up common test data
        self.client = Client()
        self.program = Program.objects.create(name="Test Program")
        
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        
        # Create an event
        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.tomorrow,
            registration_closes_at=self.tomorrow,
            has_rides=True,
            ride_leaders_wanted=True,
            requires_emergency_contact=True
        )
        
        # Create a ride for the event
        self.ride = Ride.objects.create(
            event=self.event,
            name="Test Ride",
            description="Test Ride Description"
        )
        
        # Create a speed range
        self.speed_range = SpeedRange.objects.create(
            name="Test Speed Range",
            min_speed=15,
            max_speed=20
        )
        
        # Registration URL
        self.registration_url = reverse('registration_create', args=[self.event.id])
        
        # Standard registration data for tests
        self.registration_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'ride_leader_preference': Registration.RIDE_LEADER_NO,
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '123-456-7890'
        }
        
    def test_registration_create_view_get(self):
        """Test that the registration create view returns a 200 status code."""
        response = self.client.get(self.registration_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registration.html')
        self.assertContains(response, self.event.name)
        
    def test_registration_create_view_post_success(self):
        """Test that the registration create view creates a registration."""
        response = self.client.post(self.registration_url, self.registration_data)
        
        # Should redirect to the registration submitted page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # Check that a registration was created
        self.assertEqual(Registration.objects.count(), 1)
        registration = Registration.objects.first()
        
        # Check registration details
        self.assertEqual(registration.name, 'Test User')
        self.assertEqual(registration.email, 'test@example.com')
        self.assertEqual(registration.event, self.event)
        self.assertEqual(registration.ride, self.ride)
        self.assertEqual(registration.speed_range_preference, self.speed_range)
        self.assertEqual(registration.ride_leader_preference, Registration.RIDE_LEADER_NO)
        self.assertEqual(registration.emergency_contact_name, 'Emergency Contact')
        self.assertEqual(registration.emergency_contact_phone, '123-456-7890')
        
        # Check that registration state is CONFIRMED (after email)
        self.assertEqual(registration.state, Registration.STATE_CONFIRMED)
        
        # Check that user was created
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        
    def test_rule_no_registration_exists(self):
        """Test: If no registration record exists, create a new registration."""
        # This case is already covered in test_registration_create_view_post_success
        # But adding an explicit rule-based test for clarity
        response = self.client.post(self.registration_url, self.registration_data)
        
        self.assertRedirects(response, reverse('registration_submitted'))
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Registration.objects.first().state, Registration.STATE_CONFIRMED)
    
    def test_rule_withdrawn_registration_exists(self):
        """Test: If a withdrawn registration exists, create a new registration."""
        # Create user and withdrawn registration
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='password123'
        )
        
        registration = Registration.objects.create(
            name='Test User',
            email='test@example.com',
            event=self.event,
            user=user,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            state=Registration.STATE_SUBMITTED
        )
        registration.confirm()
        registration.withdraw()
        registration.save()
        
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(registration.state, Registration.STATE_WITHDRAWN)
        
        # Attempt to register again
        response = self.client.post(self.registration_url, self.registration_data)
        
        # Should redirect to success page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # Should create a new registration
        self.assertEqual(Registration.objects.count(), 2)
        
        # Most recent registration should be confirmed
        latest_registration = Registration.objects.latest('submitted_at')
        self.assertEqual(latest_registration.state, Registration.STATE_CONFIRMED)
    
    def test_rule_submitted_registration_exists(self):
        """Test: If a submitted registration exists, do nothing."""
        # Create user and submitted registration
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='password123'
        )
        
        registration = Registration.objects.create(
            name='Test User',
            email='test@example.com',
            event=self.event,
            user=user,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            state=Registration.STATE_SUBMITTED
        )
        
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(registration.state, Registration.STATE_SUBMITTED)
        
        # Attempt to register again
        response = self.client.post(self.registration_url, self.registration_data)
        
        # Should redirect to success page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # Should not create a new registration
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Registration.objects.first().state, Registration.STATE_SUBMITTED)
    
    def test_rule_confirmed_registration_exists(self):
        """Test: If a confirmed registration exists, do nothing."""
        # This case is covered by test_duplicate_registration_handling
        # But adding an explicit rule-based test for clarity
        
        # Create user and confirmed registration
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='password123'
        )
        
        registration = Registration.objects.create(
            name='Test User',
            email='test@example.com',
            event=self.event,
            user=user,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            state=Registration.STATE_SUBMITTED
        )
        registration.confirm()
        registration.save()
        
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(registration.state, Registration.STATE_CONFIRMED)
        
        # Attempt to register again
        response = self.client.post(self.registration_url, self.registration_data)
        
        # Should redirect to success page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # Should not create a new registration
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Registration.objects.first().state, Registration.STATE_CONFIRMED)
        
    def test_duplicate_registration_handling(self):
        """Test that attempting to register twice doesn't create duplicate registrations."""
        # Create a user
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        # Create an initial registration
        registration = Registration.objects.create(
            name='Test User',
            email='test@example.com',
            event=self.event,
            user=user,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RIDE_LEADER_NO,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='123-456-7890'
        )
        registration.confirm()
        registration.save()
        
        # Try to register again with same email
        response = self.client.post(self.registration_url, self.registration_data)
        
        # Should still redirect to success page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # But no new registration should be created
        self.assertEqual(Registration.objects.count(), 1)
        
    def test_withdrawn_registration_recreation(self):
        """Test that a withdrawn registration can be recreated."""
        # Create a user
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        # Create an initial registration
        registration = Registration.objects.create(
            name='Test User',
            email='test@example.com',
            event=self.event,
            user=user,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RIDE_LEADER_NO,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='123-456-7890'
        )
        registration.confirm()
        registration.withdraw()
        registration.save()
        
        # Try to register again with same email
        registration_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            'ride_leader_preference': Registration.RIDE_LEADER_NO,
            'emergency_contact_name': 'New Emergency Contact',
            'emergency_contact_phone': '987-654-3210'
        }
        
        response = self.client.post(self.registration_url, registration_data)
        
        # Should redirect to success page
        self.assertRedirects(response, reverse('registration_submitted'))
        
        # Should now have two registrations (one withdrawn, one confirmed)
        self.assertEqual(Registration.objects.count(), 2)
        
        # The new registration should be confirmed
        new_registration = Registration.objects.latest('submitted_at')
        self.assertEqual(new_registration.state, Registration.STATE_CONFIRMED)
        self.assertEqual(new_registration.emergency_contact_name, 'New Emergency Contact')
        self.assertEqual(new_registration.emergency_contact_phone, '987-654-3210')
        
    def test_invalid_form_submission(self):
        """Test handling of invalid form data."""
        # Missing required fields
        registration_data = {
            'name': 'Test User',
            # Missing email
            'ride': self.ride.id,
            'speed_range_preference': self.speed_range.id,
            # Missing emergency contact fields
        }
        
        response = self.client.post(self.registration_url, registration_data)
        
        # Should return to form with errors
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'web/events/registration.html')
        
        # No registration should be created
        self.assertEqual(Registration.objects.count(), 0) 