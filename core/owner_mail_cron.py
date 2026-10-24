"""Vercel Cron entrypoints for the existing bounded owner-mail outbox.

Only Vercel's CRON_SECRET bearer is accepted. Never return links, addresses,
challenge identifiers or provider exceptions.
"""
from __future__ import annotations

import hmac
import os
from django.conf import settings
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache


def _authorized(request):
    secret = os.environ.get("CRON_SECRET", "")
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        return False
    header = request.headers.get("Authorization", "")
    return hmac.compare_digest(header, "Bearer " + secret)


@csrf_exempt
@never_cache
def dispatch_owner_mail_cron(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    from core.owner_mail_worker import dispatch_one, worker_enabled
    if not worker_enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    counts = {"delivered": 0, "retry": 0, "discarded": 0}
    try:
        for _ in range(5):
            result = dispatch_one()
            if result == "idle":
                break
            if result not in counts:
                return JsonResponse({"error": "unavailable"}, status=503)
            counts[result] += 1
    except Exception:
        return JsonResponse({"error": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "counts": counts})


@csrf_exempt
@never_cache
def maintain_owner_mail_cron(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    from core.owner_mail_maintenance import maintenance_enabled, sweep_owner_mail
    if not maintenance_enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    try:
        discarded, pruned = sweep_owner_mail(batch=100)
    except Exception:
        return JsonResponse({"error": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "discarded": discarded, "pruned": pruned})
