from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from audit.context import get_actor
from audit.services import AuditService
from .models import (
    Announcement,
    Event,
    Program,
    Registration,
    Ride,
    Route,
    SpeedRange,
    UserMembershipNumber,
    UserProfile,
)


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


AUDITED_MODELS = (
    Program,
    Event,
    Route,
    SpeedRange,
    Ride,
    UserProfile,
    UserMembershipNumber,
    Registration,
    Announcement,
)


def log_audited_save(sender, instance, created, **kwargs):
    actor = get_actor()
    if actor is None:
        return
    AuditService().log(actor, 'created' if created else 'updated', target=instance)


def log_audited_delete(sender, instance, **kwargs):
    actor = get_actor()
    if actor is None:
        return
    AuditService().log(actor, 'deleted', target=instance)


for model in AUDITED_MODELS:
    post_save.connect(log_audited_save, sender=model,
                      dispatch_uid=f'audit_save_{model.__name__}')
    post_delete.connect(log_audited_delete, sender=model,
                        dispatch_uid=f'audit_delete_{model.__name__}')