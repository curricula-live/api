from django.contrib import admin

from core.models import Concept, Relation, RelationType


class ImmutablePrimaryKeyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return (self.model._meta.pk.name,)


@admin.register(Concept)
class ConceptAdmin(ImmutablePrimaryKeyAdmin):
    search_fields = ("slug",)
    ordering = ("slug",)


@admin.register(RelationType)
class RelationTypeAdmin(ImmutablePrimaryKeyAdmin):
    search_fields = ("slug",)
    ordering = ("slug",)


@admin.register(Relation)
class RelationAdmin(ImmutablePrimaryKeyAdmin):
    list_display = ("source", "type", "target")
    list_filter = ("type",)
    search_fields = ("source__slug", "target__slug", "type__slug")
    ordering = ("source_id", "type_id", "target_id")
    autocomplete_fields = ("source", "type", "target")
