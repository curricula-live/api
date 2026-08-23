from django.contrib import admin

from core.models import Concept, Relation, RelationType


@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    search_fields = ("slug",)
    ordering = ("slug",)


@admin.register(RelationType)
class RelationTypeAdmin(admin.ModelAdmin):
    search_fields = ("slug",)
    ordering = ("slug",)


@admin.register(Relation)
class RelationAdmin(admin.ModelAdmin):
    list_display = ("source", "type", "target")
    list_filter = ("type",)
    search_fields = ("source__slug", "target__slug", "type__slug")
    ordering = ("source_id", "type_id", "target_id")
    autocomplete_fields = ("source", "type", "target")
