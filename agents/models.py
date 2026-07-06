from django.db import models


class AgentRequest(models.Model):
    class Kind(models.TextChoices):
        CRAWLER = 'crawler'
        ASSISTANT = 'assistant'
        SCRIPT = 'script'
        PROBE = 'probe'

    family = models.CharField(max_length=50)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    user_agent = models.CharField(max_length=512, blank=True)
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField()
    probe = models.BooleanField(default=False)
    authenticated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['family', 'created_at']),
        ]

    def __str__(self):
        return f'{self.family} {self.method} {self.path}'
