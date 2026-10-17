"""Additive release storage; never alters canonical graph tables."""
from django.db import models


class ScholarlyRelease(models.Model):
    source_id = models.CharField(max_length=32)
    version = models.CharField(max_length=128)
    sha256 = models.CharField(max_length=64, unique=True)
    payload = models.JSONField()
    installed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('source_id', 'version'), name='unique_scholarly_source_version')]
