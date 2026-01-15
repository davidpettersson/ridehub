from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Group

from backoffice.adapters import RideHubSocialAccountAdapter


class TestRideHubSocialAccountAdapterConfigureObcUser(TestCase):
    def setUp(self):
        self.adapter = RideHubSocialAccountAdapter()
        self.group, _ = Group.objects.get_or_create(name='Ride Administrators')

    def test_configure_obc_user_sets_staff_for_obc_domain(self):
        user = User.objects.create_user(
            username='volunteer@ottawabicycleclub.ca',
            email='volunteer@ottawabicycleclub.ca',
            first_name='Test',
            last_name='Volunteer'
        )

        self.adapter._configure_obc_user(user)

        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_configure_obc_user_adds_to_ride_administrators_group(self):
        user = User.objects.create_user(
            username='volunteer@ottawabicycleclub.ca',
            email='volunteer@ottawabicycleclub.ca',
            first_name='Test',
            last_name='Volunteer'
        )

        self.adapter._configure_obc_user(user)

        self.assertTrue(user.groups.filter(name='Ride Administrators').exists())

    def test_configure_obc_user_skips_non_obc_domain(self):
        user = User.objects.create_user(
            username='member@gmail.com',
            email='member@gmail.com',
            first_name='Regular',
            last_name='Member'
        )

        self.adapter._configure_obc_user(user)

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.groups.filter(name='Ride Administrators').exists())

    def test_configure_obc_user_handles_uppercase_email(self):
        user = User.objects.create_user(
            username='VOLUNTEER@OTTAWABICYCLECLUB.CA',
            email='VOLUNTEER@OTTAWABICYCLECLUB.CA',
            first_name='Test',
            last_name='Volunteer'
        )

        self.adapter._configure_obc_user(user)

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.groups.filter(name='Ride Administrators').exists())

    def test_configure_obc_user_idempotent_for_existing_group_member(self):
        user = User.objects.create_user(
            username='volunteer@ottawabicycleclub.ca',
            email='volunteer@ottawabicycleclub.ca',
            first_name='Test',
            last_name='Volunteer'
        )
        user.groups.add(self.group)

        self.adapter._configure_obc_user(user)

        self.assertEqual(user.groups.filter(name='Ride Administrators').count(), 1)


class TestRideHubSocialAccountAdapterConfigureObcUserMissingGroup(TestCase):
    def setUp(self):
        self.adapter = RideHubSocialAccountAdapter()

    @override_settings(AZURE_AD_STAFF_GROUP='Nonexistent Group')
    def test_configure_obc_user_raises_when_group_missing(self):
        user = User.objects.create_user(
            username='volunteer@ottawabicycleclub.ca',
            email='volunteer@ottawabicycleclub.ca',
            first_name='Test',
            last_name='Volunteer'
        )

        with self.assertRaises(Group.DoesNotExist):
            self.adapter._configure_obc_user(user)


class TestRideHubSocialAccountAdapterPopulateUser(TestCase):
    def setUp(self):
        self.adapter = RideHubSocialAccountAdapter()

    def test_populate_user_lowercases_email(self):
        sociallogin = MagicMock()
        request = MagicMock()
        data = {'email': 'TEST@EXAMPLE.COM', 'first_name': 'Test', 'last_name': 'User'}

        user = self.adapter.populate_user(request, sociallogin, data)

        self.assertEqual(user.email, 'test@example.com')

    def test_populate_user_handles_empty_email(self):
        sociallogin = MagicMock()
        request = MagicMock()
        data = {'first_name': 'Test', 'last_name': 'User'}

        user = self.adapter.populate_user(request, sociallogin, data)

        self.assertEqual(user.email, '')
