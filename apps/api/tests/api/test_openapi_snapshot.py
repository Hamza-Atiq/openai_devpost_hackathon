from __future__ import annotations

import hashlib
import json

from app.main import create_app

OPENAPI_V1_SHA256 = "367e6cfa9a3de1248cb896c47770692bc80819e9273bc2dc9682e45d8c9a059b"


def test_openapi_v1_canonical_snapshot() -> None:
    document = create_app().openapi()
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == OPENAPI_V1_SHA256
