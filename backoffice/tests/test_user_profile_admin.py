from django.contrib.auth.models import User
from django.test import TestCase

from backoffice.admin import UserProfileAdmin
from backoffice.models import UserProfile


class UserProfileAdminTestCase(TestCase):
    def setUp(self):
        # Arrange
        self.user = User.objects.create_user(username='rider', email='rider@example.com')
        self.admin = UserProfileAdmin(UserProfile, admin_site=None)

    def test_delete_permission_denied_for_profile(self):
        # Act
        allowed = self.admin.has_delete_permission(request=None, obj=self.user.profile)

        # Assert
        self.assertFalse(allowed)

    def test_deleting_user_still_cascades_to_profile(self):
        # Act
        self.user.delete()

        # Assert
        self.assertFalse(UserProfile.objects.filter(user_id=self.user.id).exists())
