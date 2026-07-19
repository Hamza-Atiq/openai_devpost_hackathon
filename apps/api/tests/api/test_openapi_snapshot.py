from __future__ import annotations

import hashlib
import json

from app.main import create_app

OPENAPI_V1_SHA256 = "dd032afdf5915a77565c8299eae7053363769f657cd80a3c395247a95a9109dc"


def test_openapi_v1_canonical_snapshot() -> None:
    document = create_app().openapi()
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == OPENAPI_V1_SHA256
