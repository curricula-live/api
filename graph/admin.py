from django.contrib import admin, messages
from django.db import connection, transaction
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import path
from .models import Concept, Relation

@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ("slug", "label", "updated_at")
    search_fields = ("slug", "label", "description")
    ordering = ("slug",)
    actions = ["export_selected_json"]

    @admin.action(description="Export selected concepts as JSON")
    def export_selected_json(self, request, queryset):
        return JsonResponse(list(queryset.values("slug", "label", "description", "metadata")), safe=False)

@admin.register(Relation)
class RelationAdmin(admin.ModelAdmin):
    list_display = ("source", "type", "target", "updated_at")
    list_filter = ("type",)
    search_fields = ("source__slug", "target__slug", "type")
    autocomplete_fields = ("source", "target")

class GraphAdminSite(admin.AdminSite):
    site_header = "curricula.live knowledge graph"
    site_title = "curricula.live admin"
    index_title = "Concept and relation management"

    def get_urls(self):
        return [
            path("graph/", self.admin_view(self.graph_view), name="graph-view"),
            path("sql/", self.admin_view(self.sql_view), name="sql-workbench"),
        ] + super().get_urls()

    def graph_view(self, request):
        nodes = list(Concept.objects.values("id", "slug", "label"))
        edges = [{"from": r.source_id, "to": r.target_id, "label": r.type, "arrows": "to"}
                 for r in Relation.objects.all()]
        return TemplateResponse(request, "admin/graph/visualization.html", {**self.each_context(request), "nodes": nodes, "edges": edges})

    def sql_view(self, request):
        result, columns, error = [], [], None
        sql = request.POST.get("sql", "")
        allow_write = request.POST.get("allow_write") == "on"
        if request.method == "POST" and sql:
            first = sql.lstrip().split(None, 1)[0].lower() if sql.strip() else ""
            if first not in {"select", "with", "explain"} and not allow_write:
                error = "Write statements require explicit confirmation."
            else:
                try:
                    with transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = '5s'")
                        cursor.execute(sql)
                        if cursor.description:
                            columns = [c.name for c in cursor.description]
                            result = cursor.fetchmany(500)
                        messages.success(request, "SQL executed in a transaction.")
                except Exception as exc:
                    error = str(exc)
        return TemplateResponse(request, "admin/graph/sql_workbench.html", {**self.each_context(request), "sql": sql, "columns": columns, "rows": result, "error": error})
