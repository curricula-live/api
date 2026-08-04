import os

# Tests must never use the developer or deployed DATABASE_URL.
os.environ["DATABASE_URL"] = "sqlite://:memory:"
os.environ["DJANGO_SECRET_KEY"] = "django-insecure-test-suite-only"
os.environ["DJANGO_DEBUG"] = "false"

from .settings import *  # noqa: E402,F401,F403
