from django.contrib.contenttypes.models import ContentType

from backoffice.models import Notification


class NotificationService:
    def record(self, kind: str, recipients: list[str], target=None) -> Notification:
        notification = Notification(kind=kind, recipients=list(recipients))

        if target is not None:
            notification.target_content_type = ContentType.objects.get_for_model(target)
            notification.target_object_id = target.pk
            notification.target_repr = f'{target._meta.verbose_name.capitalize()} #{target.pk}'

        notification.full_clean()
        notification.save()
        return notification

    def has_been_sent(self, kind: str, target) -> bool:
        return Notification.objects.filter(
            kind=kind,
            target_content_type=ContentType.objects.get_for_model(target),
            target_object_id=target.pk,
        ).exists()

    def targets_already_notified(self, kind: str, model, target_ids: list[int]) -> set[int]:
        return set(
            Notification.objects.filter(
                kind=kind,
                target_content_type=ContentType.objects.get_for_model(model),
                target_object_id__in=target_ids,
            ).values_list('target_object_id', flat=True)
        )
