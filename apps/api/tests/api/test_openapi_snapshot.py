from __future__ import annotations

import hashlib
import json

from app.main import create_app

OPENAPI_V1_SHA256 = "ad426581a5d33f412a155a8d243044f188aa203dca81070c93249a938b90ca15"


def test_openapi_v1_canonical_snapshot() -> None:
    document = create_app().openapi()
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == OPENAPI_V1_SHA256
