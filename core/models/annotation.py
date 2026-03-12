import uuid
from django.db import models


class Annotation(models.Model):
    class AnnotationType(models.TextChoices):
        FRAME = 'frame'
        TIMESTAMP = 'timestamp'

    class Source(models.TextChoices):
        MANUAL = 'manual'
        AUTO = 'auto'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(
        'core.Video',
        on_delete=models.CASCADE,
        related_name='annotations',
    )
    type = models.CharField(max_length=20, choices=AnnotationType.choices)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    frame_number = models.IntegerField(null=True, blank=True, help_text='Set when type=frame')
    timestamp = models.FloatField(null=True, blank=True, help_text='Seconds into video, set when type=timestamp')
    content = models.TextField(help_text='Annotation text/data', default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['timestamp', 'frame_number', 'created_at']
        indexes = [
            models.Index(fields=['video', 'source'], name='idx_annotation_video_source'),
            models.Index(fields=['video', 'source', 'timestamp'], name='idx_annotation_video_src_ts'),
        ]

    def __str__(self):
        return f'{self.type} annotation on {self.video.title}'
