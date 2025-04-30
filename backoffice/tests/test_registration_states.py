from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Program, Event, Registration


class RegistrationStatesTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Test Program")
        
        self.now = timezone.now()
        self.tomorrow = self.now + timedelta(days=1)
        self.yesterday = self.now - timedelta(days=1)
        
        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=self.tomorrow,
            registration_closes_at=self.now
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        self.registration = Registration.objects.create(
            name="Test User",
            email="test@example.com",
            event=self.event,
            user=self.user
        )

    def test_initial_state(self):
        self.assertEqual(self.registration.state, 'submitted')
        self.assertIsNotNone(self.registration.submitted_at)
        self.assertIsNone(self.registration.confirmed_at)
        self.assertIsNone(self.registration.withdrawn_at)
        self.assertIsNone(self.registration.registered_at)

    def test_confirm(self):
        self.assertEqual(self.registration.state, 'submitted')

        self.registration.confirm()
        self.registration.save()
        
        self.assertEqual(self.registration.state, 'confirmed')
        self.assertIsNotNone(self.registration.confirmed_at)
        self.assertGreaterEqual(
            self.registration.confirmed_at,
            self.registration.submitted_at
        )

    def test_withdraw(self):
        self.registration.confirm()
        self.registration.save()
        
        self.assertEqual(self.registration.state, 'confirmed')
        
        self.registration.withdraw()
        self.registration.save()
        
        self.assertEqual(self.registration.state, 'withdrawn')
        self.assertIsNotNone(self.registration.withdrawn_at)
        self.assertGreaterEqual(
            self.registration.withdrawn_at,
            self.registration.confirmed_at
        )

    def test_resubmit(self):
        self.registration.confirm()
        self.registration.withdraw()
        self.registration.save()

        self.assertEqual(self.registration.state, 'withdrawn')

        initial_submitted_at = self.registration.submitted_at
        self.registration.resubmit()
        self.registration.save()
        
        self.assertEqual(self.registration.state, 'submitted')
        self.assertGreaterEqual(
            self.registration.submitted_at,
            initial_submitted_at
        )

    def test_cannot_withdraw_from_submitted(self):
        self.assertEqual(self.registration.state, 'submitted')
        with self.assertRaises(Exception):
            self.registration.withdraw()
            
    def test_cannot_resubmit_from_submitted(self):
        self.assertEqual(self.registration.state, 'submitted')
        with self.assertRaises(Exception):
            self.registration.resubmit()
        
    def test_cannot_confirm_already_confirmed(self):
        self.registration.confirm()
        self.registration.save()
        self.assertEqual(self.registration.state, 'confirmed')
        
        with self.assertRaises(Exception):
            self.registration.confirm()
            
    def test_cannot_resubmit_from_confirmed(self):
        self.registration.confirm()
        self.registration.save()
        self.assertEqual(self.registration.state, 'confirmed')
        
        with self.assertRaises(Exception):
            self.registration.resubmit()
            
    def test_cannot_withdraw_already_withdrawn(self):
        self.registration.confirm()
        self.registration.withdraw()
        self.registration.save()
        self.assertEqual(self.registration.state, 'withdrawn')
        
        with self.assertRaises(Exception):
            self.registration.withdraw()
            
    def test_cannot_confirm_withdrawn(self):
        self.registration.confirm()
        self.registration.withdraw()
        self.registration.save()
        self.assertEqual(self.registration.state, 'withdrawn')
        
        with self.assertRaises(Exception):
            self.registration.confirm() 