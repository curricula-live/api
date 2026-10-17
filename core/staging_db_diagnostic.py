"""Read-only staging DB diagnostic. Returns no identity, SQL, or secrets."""
import hmac
from django.conf import settings
from django.db import connection
from django.http import JsonResponse, Http404

def staging_database_health(request):
    if request.method != "GET" or settings.APP_ENV != "staging" or settings.IS_PRODUCTION:
        raise Http404()
    expected = settings.OWNER_BFF_SHARED_SECRET
    provided = request.headers.get("X-Admin-BFF-Secret", "")
    if not expected or len(expected) < 32 or not hmac.compare_digest(provided, expected):
        raise Http404()
    report = {"connectivity": False, "knowledge_read": False, "owner_read": False, "rate_bucket_write": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("select 1")
            report["connectivity"] = True
            cursor.execute("select 1 from knowledge.publication limit 1")
            report["knowledge_read"] = True
            cursor.execute("select 1 from admin.owner_principal limit 1")
            report["owner_read"] = True
            cursor.execute("select has_table_privilege(current_user,'admin.owner_auth_rate_bucket','INSERT') and has_table_privilege(current_user,'admin.owner_auth_rate_bucket','UPDATE')")
            report["rate_bucket_write"] = cursor.fetchone()[0] is True
    except Exception as exc:
        report["failure_category"] = type(exc).__name__
    response = JsonResponse(report, status=200 if all(report.values()) else 503)
    response["Cache-Control"] = "private, no-store"
    return response
