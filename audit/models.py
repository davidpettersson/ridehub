from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class StandardAction(models.TextChoices):
    CREATED = 'created', 'Created'
    UPDATED = 'updated', 'Updated'
    DELETED = 'deleted', 'Deleted'
    ARCHIVED = 'archived', 'Archived'
    REVEALED = 'revealed', 'Revealed'


class AuditEvent(models.Model):
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='audit_events',
    )
    action = models.CharField(max_length=50)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')
    target_repr = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['subject']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        if self.target_repr:
            return f'{self.subject} {self.action} {self.target_repr}'
        return f'{self.subject} {self.action}'
