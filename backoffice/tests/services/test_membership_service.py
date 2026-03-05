from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import UserMembershipNumber
from backoffice.services.membership_service import MembershipService


class MembershipServiceTests(TestCase):
    def setUp(self):
        self.service = MembershipService()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            first_name='Test',
            last_name='User',
        )

    def test_get_current_membership_number_returns_latest_for_current_year(self):
        # Arrange
        current_year = timezone.now().year
        UserMembershipNumber.objects.create(user=self.user, number='OBC-OLD', year=current_year)
        UserMembershipNumber.objects.create(user=self.user, number='OBC-NEW', year=current_year)

        # Act
        result = self.service.get_current_membership_number(self.user)

        # Assert
        self.assertEqual(result.number, 'OBC-NEW')

    def test_get_current_membership_number_returns_none_when_no_records(self):
        # Act
        result = self.service.get_current_membership_number(self.user)

        # Assert
        self.assertIsNone(result)

    def test_get_current_membership_number_returns_none_for_old_year_only(self):
        # Arrange
        UserMembershipNumber.objects.create(user=self.user, number='OBC-OLD', year=2020)

        # Act
        result = self.service.get_current_membership_number(self.user)

        # Assert
        self.assertIsNone(result)

    def test_has_current_membership_number_true(self):
        # Arrange
        UserMembershipNumber.objects.create(
            user=self.user, number='OBC-123', year=timezone.now().year
        )

        # Act & Assert
        self.assertTrue(self.service.has_current_membership_number(self.user))

    def test_has_current_membership_number_false(self):
        # Act & Assert
        self.assertFalse(self.service.has_current_membership_number(self.user))

    def test_save_membership_number_creates_record(self):
        # Act
        result = self.service.save_membership_number(self.user, 'OBC-54321')

        # Assert
        self.assertEqual(result.number, 'OBC-54321')
        self.assertEqual(result.year, timezone.now().year)
        self.assertEqual(result.user, self.user)

    def test_save_membership_number_strips_whitespace(self):
        # Act
        result = self.service.save_membership_number(self.user, '  OBC-54321  ')

        # Assert
        self.assertEqual(result.number, 'OBC-54321')

    def test_save_membership_number_is_idempotent(self):
        # Arrange
        self.service.save_membership_number(self.user, 'OBC-FIRST')

        # Act
        result = self.service.save_membership_number(self.user, 'OBC-FIRST')

        # Assert
        self.assertEqual(
            UserMembershipNumber.objects.filter(user=self.user, year=timezone.now().year).count(), 1
        )
        self.assertEqual(result.number, 'OBC-FIRST')

    def test_save_membership_number_updates_existing_if_different(self):
        # Arrange
        self.service.save_membership_number(self.user, 'OBC-OLD')

        # Act
        result = self.service.save_membership_number(self.user, 'OBC-NEW')

        # Assert
        self.assertEqual(
            UserMembershipNumber.objects.filter(user=self.user, year=timezone.now().year).count(), 1
        )
        self.assertEqual(result.number, 'OBC-NEW')
