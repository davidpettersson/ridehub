from django.test import TestCase
from django.contrib.auth.models import User
from returns.maybe import Some, Nothing

from backoffice.services.user_service import UserService, UserDetail


class TestUserService(TestCase):
    def setUp(self):
        self.service = UserService()
        self.test_email = "test@example.com"
        self.test_user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.test_email
        )

    def test_find_by_email_when_user_exists(self):
        # Arrange
        User.objects.create_user(
            username=self.test_email,
            email=self.test_email,
            first_name="Existing",
            last_name="User"
        )

        # Act
        result = self.service.find_by_email(self.test_email)

        # Assert
        self.assertIsInstance(result, Some)
        user = result.unwrap()
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Existing")
        self.assertEqual(user.last_name, "User")

    def test_find_by_email_when_user_does_not_exist(self):
        # Act
        result = self.service.find_by_email(self.test_email)

        # Assert
        self.assertEqual(Nothing, result)

    def test_find_by_email_or_create_when_user_does_not_exist(self):
        # Act
        user = self.service.find_by_email_or_create(self.test_user_detail)

        # Assert
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)

    def test_find_by_email_or_create_when_non_staff_user_exists(self):
        # Arrange
        existing_user = User.objects.create_user(
            username=self.test_email,
            email=self.test_email,
            first_name="Old",
            last_name="Name"
        )
        existing_user.set_unusable_password()
        existing_user.save()

        # Act
        user = self.service.find_by_email_or_create(self.test_user_detail)

        # Assert
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Test")  # Should be updated
        self.assertEqual(user.last_name, "User")   # Should be updated
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)

    def test_find_by_email_or_create_when_staff_user_exists(self):
        # Arrange
        existing_user = User.objects.create_user(
            username=self.test_email,
            email=self.test_email,
            first_name="Old",
            last_name="Name"
        )
        existing_user.is_staff = True
        existing_user.set_unusable_password()
        existing_user.save()

        # Act
        user = self.service.find_by_email_or_create(self.test_user_detail)

        # Assert
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Old")  # Should not be updated
        self.assertEqual(user.last_name, "Name")  # Should not be updated
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_staff) 