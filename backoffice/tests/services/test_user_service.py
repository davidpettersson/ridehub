from django.test import TestCase
from django.contrib.auth.models import User
from returns.maybe import Some, Nothing

from backoffice.models import UserProfile
from backoffice.services.user_service import UserService, UserDetail


class TestUserServiceFindByEmail(TestCase):
    def setUp(self):
        self.service = UserService()
        self.test_email = "test@example.com"
        User.objects.create_user(
            username=self.test_email,
            email=self.test_email,
            first_name="Existing",
            last_name="User"
        )
        
        self.lower_case_email_casing = "findcasing@example.com"
        User.objects.create_user(
            username=self.lower_case_email_casing,
            email=self.lower_case_email_casing,
            first_name="Existing",
            last_name="CasingUser"
        )

    def test_find_by_email_when_user_exists(self):
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
        result = self.service.find_by_email("nonexistent@example.com")

        # Assert
        self.assertEqual(Nothing, result)

    def test_find_by_email_with_different_casing(self):
        # Arrange
        upper_case_email = "FINDcasING@EXAMPLE.COM"
        mixed_case_email = "FindCasing@Example.com"

        # Act & Assert - Find using upper case
        result_upper = self.service.find_by_email(upper_case_email)
        self.assertIsInstance(result_upper, Some)
        self.assertEqual(result_upper.unwrap().email, self.lower_case_email_casing)

        # Act & Assert - Find using mixed case
        result_mixed = self.service.find_by_email(mixed_case_email)
        self.assertIsInstance(result_mixed, Some)
        self.assertEqual(result_mixed.unwrap().email, self.lower_case_email_casing)


class TestUserServiceFindByEmailOrCreate(TestCase):
    def setUp(self):
        self.service = UserService()
        self.test_email = "test@example.com"
        self.test_phone = "+16131231234"
        self.test_user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.test_email,
            phone=self.test_phone,
        )
        
        # User for non-staff update test
        self.non_staff_email = "nonstaffupdate@example.com"
        User.objects.create_user(
            username=self.non_staff_email,
            email=self.non_staff_email,
            first_name="Old",
            last_name="Name"
        ).set_unusable_password()
        
        # User for staff no-update test
        self.staff_email = "staffnoupdate@example.com"
        staff_user = User.objects.create_user(
            username=self.staff_email,
            email=self.staff_email,
            first_name="Old",
            last_name="Name",
            is_staff=True
        )
        staff_user.set_unusable_password()
        staff_user.save()
        
        # Users for casing test
        self.non_staff_casing_email = "nonstaffcasing@example.com"
        User.objects.create_user(
            username=self.non_staff_casing_email,
            email=self.non_staff_casing_email,
            first_name="OldNon",
            last_name="Staff"
        )
        self.staff_casing_email = "staffcasing@example.com"
        staff_casing_user = User.objects.create_user(
            username=self.staff_casing_email,
            email=self.staff_casing_email,
            first_name="Old",
            last_name="Staff",
            is_staff=True
        )
        staff_casing_user.save()

    def test_find_by_email_or_create_when_user_does_not_exist(self):
        # Act
        user = self.service.find_by_email_or_create(self.test_user_detail)

        # Assert
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        # Check it was actually created
        self.assertTrue(User.objects.filter(email=self.test_email).exists())

    def test_find_by_email_or_create_when_non_staff_user_exists(self):
        # Arrange
        user_detail_upper = UserDetail(
            first_name="Test",
            last_name="User",
            email="NONSTAFFUPDATE@EXAMPLE.COM", # Upper case email
            phone="+16131112222"
        )

        # Act
        user = self.service.find_by_email_or_create(user_detail_upper)

        # Assert
        self.assertEqual(user.email, self.non_staff_email) # Original email
        self.assertEqual(user.first_name, "Test")  # Should be updated
        self.assertEqual(user.last_name, "User")   # Should be updated
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)

    def test_find_by_email_or_create_when_staff_user_exists(self):
        # Arrange
        user_detail_mixed = UserDetail(
            first_name="Test",
            last_name="User",
            email="StaffNoUpdate@Example.com", # Mixed case email
            phone="+16131112222"
        )
        
        # Act
        user = self.service.find_by_email_or_create(user_detail_mixed)

        # Assert
        self.assertEqual(user.email, self.staff_email) # Original email
        self.assertEqual(user.first_name, "Old")  # Should not be updated
        self.assertEqual(user.last_name, "Name")  # Should not be updated
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_staff)

    def test_find_by_email_or_create_with_different_casing_updates_non_staff(self):
        # Arrange
        non_staff_detail_upper = UserDetail("NewNon", "Staff", "NONSTAFFCASING@EXAMPLE.COM", "+16131112222")
        
        # Act
        updated_non_staff = self.service.find_by_email_or_create(non_staff_detail_upper)
        
        # Assert
        self.assertEqual(updated_non_staff.email, self.non_staff_casing_email)
        self.assertEqual(updated_non_staff.first_name, "NewNon") # Updated
        self.assertEqual(updated_non_staff.last_name, "Staff") # Updated
        self.assertFalse(updated_non_staff.is_staff)

    def test_find_by_email_or_create_with_different_casing_does_not_update_staff(self):
        # Arrange
        staff_detail_mixed = UserDetail("New", "Staff", "StaffCasing@Example.com", "+16131112222")
        
        # Act
        found_staff = self.service.find_by_email_or_create(staff_detail_mixed)
        
        # Assert
        self.assertEqual(found_staff.email, self.staff_casing_email)
        self.assertEqual(found_staff.first_name, "Old") # Not updated
        self.assertEqual(found_staff.last_name, "Staff") # Not updated
        self.assertTrue(found_staff.is_staff) 