"""Unmanaged v2 read-model matching data-owned knowledge.concept DDL.

This model is deliberately NOT a migration source. The `data` repository owns
the knowledge schema. No public view consumes it before the coordinated cutover.
"""
from django.db import models


class V2Concept(models.Model):
    id = models.UUIDField(primary_key=True)
    slug = models.TextField(unique=True)
    label = models.TextField()

    class Meta:
        managed = False
        db_table = '"knowledge"."concept"'
        app_label = "core"

    def __str__(self) -> str:
        return self.slug
