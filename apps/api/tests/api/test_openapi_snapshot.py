from __future__ import annotations

import hashlib
import json

from app.main import create_app

OPENAPI_V1_SHA256 = "bcb1e8ac7118d27d0527530a9b4e19416a0f1d512416adfa1f487665066c2c81"


def test_openapi_v1_canonical_snapshot() -> None:
    document = create_app().openapi()
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == OPENAPI_V1_SHA256
