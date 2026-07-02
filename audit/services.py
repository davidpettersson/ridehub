from .models import AuditEvent


class AuditService:
    def log(self, actor, action, target=None):
        return AuditEvent.objects.create(
            subject=actor,
            action=action,
            target=target,
            target_repr=str(target) if target is not None else '',
        )
