from .models import AuditEvent


class AuditService:
    def log(self, actor, action, target=None):
        target_repr = ''
        if target is not None:
            target_repr = f'{target._meta.verbose_name.capitalize()} #{target.pk}'
        return AuditEvent.objects.create(
            actor=actor,
            action=action,
            target=target,
            target_repr=target_repr,
        )
