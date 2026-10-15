"""Install a reviewed public artifact into an explicitly selected development DB."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import ScholarlyRelease
from core.scholarly_contract import digest, encode, public_export


class Command(BaseCommand):
    help = 'Validate a public scholarly artifact; plan-only without --apply. Production is prohibited.'

    def add_arguments(self, parser):
        parser.add_argument('artifact', type=Path)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            raw = options['artifact'].read_bytes()
            payload = json.loads(raw)
            clean = public_export(payload)
            if encode(clean) != raw:
                raise ValueError('artifact must equal deterministic public export; unexpected fields or encoding')
            # This checkout exposes slug-only graph models. Never silently reinterpret UUIDs.
            if payload['mappings'] or payload['definitions']:
                raise ValueError('UUID canonical snapshot/resolver unavailable in this checkout; mapping/definition installation blocked')
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        source = payload['source']
        checksum = digest(raw)
        if not options['apply']:
            self.stdout.write(f"PLAN {source['id']} {source['version']} {checksum}; no writes")
            return
        if getattr(settings, 'APP_ENV', 'production') not in {'development', 'test'}:
            raise CommandError('installation is restricted to explicit development/test settings')
        with transaction.atomic():
            existing = ScholarlyRelease.objects.filter(source_id=source['id'], version=source['version']).first()
            if existing:
                if existing.sha256 != checksum:
                    raise CommandError('immutable release version already has different content')
                self.stdout.write('unchanged')
                return
            ScholarlyRelease.objects.create(source_id=source['id'], version=source['version'], sha256=checksum, payload=payload)
        self.stdout.write('installed')
