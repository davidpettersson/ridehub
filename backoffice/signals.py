from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Ensure that every User has a UserProfile. Create one if it doesn't exist.
    """
    if created:
        # User was just created, so definitely create a profile
        UserProfile.objects.create(user=instance)
    else:
        # User was updated, ensure profile exists
        try:
            # Try to access the profile to see if it exists
            instance.profile
        except UserProfile.DoesNotExist:
            # Profile doesn't exist, create it
            UserProfile.objects.create(user=instance) 