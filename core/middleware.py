from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


class CorsMiddleware:
    """Allow the configured frontend origins to call the read-only API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        origin_allowed = origin in settings.CORS_ALLOWED_ORIGINS if origin else False

        if request.method == "OPTIONS" and origin_allowed:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if not origin_allowed:
            return response

        response["Access-Control-Allow-Origin"] = origin
        patch_vary_headers(response, ("Origin",))

        if request.method == "OPTIONS":
            response["Access-Control-Allow-Methods"] = ", ".join(
                settings.CORS_ALLOWED_METHODS
            )
            response["Access-Control-Allow-Headers"] = ", ".join(
                settings.CORS_ALLOWED_HEADERS
            )
            response["Access-Control-Max-Age"] = str(settings.CORS_MAX_AGE)

        return response
