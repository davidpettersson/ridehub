from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import UserMembershipNumber


class UserMembershipNumberModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User',
        )

    def test_create_with_valid_data(self):
        # Arrange & Act
        membership = UserMembershipNumber.objects.create(
            user=self.user,
            number='OBC-12345',
            year=2026,
        )

        # Assert
        self.assertEqual(membership.number, 'OBC-12345')
        self.assertEqual(membership.year, 2026)
        self.assertEqual(membership.user, self.user)
        self.assertIsNotNone(membership.created_at)

    def test_str_representation(self):
        # Arrange
        membership = UserMembershipNumber.objects.create(
            user=self.user,
            number='OBC-99999',
            year=2026,
        )

        # Act & Assert
        self.assertEqual(str(membership), 'OBC-99999 (2026)')

    def test_ordering_by_created_at_descending(self):
        # Arrange
        first = UserMembershipNumber.objects.create(user=self.user, number='OBC-001', year=2025)
        second = UserMembershipNumber.objects.create(user=self.user, number='OBC-002', year=2026)

        # Act
        results = list(UserMembershipNumber.objects.filter(user=self.user))

        # Assert
        self.assertEqual(results[0].number, 'OBC-002')
        self.assertEqual(results[1].number, 'OBC-001')

    def test_default_year_is_current_year(self):
        # Arrange & Act
        membership = UserMembershipNumber.objects.create(
            user=self.user,
            number='OBC-DEFAULT',
        )

        # Assert
        self.assertEqual(membership.year, timezone.now().year)
