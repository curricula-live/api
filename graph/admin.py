from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import path

from .models import Concept, Relation
from .services import build_graph_payload


class ConceptAdmin(admin.ModelAdmin):
    list_display = ("slug", "label", "updated_at")
    search_fields = ("slug", "label", "description")
    ordering = ("slug",)
    actions = ["export_selected_json"]

    @admin.action(description="Export selected concepts as JSON")
    def export_selected_json(self, request, queryset):
        rows = list(
            queryset.values("id", "slug", "label", "description", "metadata")
        )
        return JsonResponse(rows, safe=False)


class RelationAdmin(admin.ModelAdmin):
    list_display = ("source", "type", "target", "updated_at")
    list_filter = ("type",)
    search_fields = ("source__slug", "target__slug", "type")
    autocomplete_fields = ("source", "target")
    list_select_related = ("source", "target")


def _single_statement(raw_sql):
    statement = raw_sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if ";" in statement:
        raise ValueError("Only one SQL statement may be executed at a time.")
    if not statement:
        raise ValueError("Enter a SQL statement.")
    return statement


class GraphAdminSite(admin.AdminSite):
    site_header = "curricula.live knowledge graph"
    site_title = "curricula.live admin"
    index_title = "Concept and relation management"
    index_template = "admin/graph/index.html"

    def get_urls(self):
        return [
            path("graph/", self.admin_view(self.graph_view), name="graph-view"),
            path("sql/", self.admin_view(self.sql_view), name="sql-workbench"),
        ] + super().get_urls()

    def graph_view(self, request):
        payload = build_graph_payload(
            query=request.GET.get("q", ""),
            relation_type=request.GET.get("type", ""),
            limit=request.GET.get("limit"),
        )
        context = {
            **self.each_context(request),
            **payload,
            "relation_types": Relation.objects.order_by("type")
            .values_list("type", flat=True)
            .distinct(),
            "title": "Knowledge graph",
        }
        return TemplateResponse(
            request,
            "admin/graph/visualization.html",
            context,
        )

    def sql_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("The SQL workbench is restricted to superusers.")

        rows = []
        columns = []
        error = None
        affected_rows = None
        result_truncated = False
        sql = request.POST.get("sql", "")
        allow_write = request.POST.get("allow_write") == "on"
        dry_run = request.POST.get("dry_run", "on") == "on"
        confirmation = request.POST.get("confirmation", "")

        if request.method == "POST":
            try:
                statement = _single_statement(sql)
                if allow_write and confirmation != "APPLY":
                    raise ValueError(
                        'Write mode requires typing "APPLY" in the confirmation field.'
                    )

                with transaction.atomic(), connection.cursor() as cursor:
                    if not allow_write:
                        cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '5s'")
                    cursor.execute("SET LOCAL lock_timeout = '1s'")
                    cursor.execute(statement)

                    affected_rows = cursor.rowcount
                    if cursor.description:
                        columns = [column.name for column in cursor.description]
                        fetched = cursor.fetchmany(501)
                        result_truncated = len(fetched) > 500
                        rows = fetched[:500]

                    if allow_write and dry_run:
                        transaction.set_rollback(True)

                if allow_write and dry_run:
                    messages.warning(request, "SQL executed, then rolled back (dry run).")
                elif allow_write:
                    messages.success(request, "SQL changes committed.")
                else:
                    messages.success(request, "Read-only SQL executed.")
            except Exception as exc:
                error = str(exc)

        context = {
            **self.each_context(request),
            "title": "SQL workbench",
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "error": error,
            "affected_rows": affected_rows,
            "result_truncated": result_truncated,
            "allow_write": allow_write,
            "dry_run": dry_run,
            "confirmation": confirmation,
        }
        return TemplateResponse(
            request,
            "admin/graph/sql_workbench.html",
            context,
        )
