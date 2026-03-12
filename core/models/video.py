import uuid
from django.db import models


class Video(models.Model):
    class SourceType(models.TextChoices):
        LOCAL_UPLOAD = 'local_upload'
        URL_UPLOAD = 'url_upload'

    class Status(models.TextChoices):
        PENDING = 'pending'
        PROCESSING = 'processing'
        READY = 'ready'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    duration = models.FloatField(null=True, blank=True)
    thumbnail_url = models.URLField(max_length=1024, null=True, blank=True)
    video_url = models.URLField(max_length=1024, null=True, blank=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    auto_annotation_interval = models.IntegerField(
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
