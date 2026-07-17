from __future__ import annotations

import hashlib
import json

from app.main import create_app

OPENAPI_V1_SHA256 = "23a6f35b3ae72c880b56e1da825a89f7b3a016bbbe714d43284e2ce7a986a927"


def test_openapi_v1_canonical_snapshot() -> None:
    document = create_app().openapi()
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == OPENAPI_V1_SHA256
