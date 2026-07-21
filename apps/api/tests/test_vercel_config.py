from __future__ import annotations

import json
from pathlib import Path


def test_vercel_disables_rewrite_cache_for_api_routes() -> None:
    config = json.loads(Path("apps/web/vercel.json").read_text(encoding="utf-8"))

    assert config["framework"] == "nextjs"
    assert "outputDirectory" not in config
    api_headers = next(item for item in config["headers"] if item["source"] == "/api/:path*")
    assert {
        "key": "x-vercel-enable-rewrite-caching",
        "value": "0",
    } in api_headers["headers"]


def test_vercel_has_one_external_api_rewrite() -> None:
    config = json.loads(Path("apps/web/vercel.json").read_text(encoding="utf-8"))

    assert config["rewrites"] == [
        {
            "source": "/api/:path*",
            "destination": "https://crickops-api-production.up.railway.app/api/:path*",
        }
    ]


def test_vercel_applies_security_headers_to_web_routes() -> None:
    config = json.loads(Path("apps/web/vercel.json").read_text(encoding="utf-8"))
    web_headers = next(item for item in config["headers"] if item["source"] == "/(.*)")
    values = {item["key"].lower(): item["value"] for item in web_headers["headers"]}

    assert values["x-content-type-options"] == "nosniff"
    assert values["x-frame-options"] == "DENY"
    assert values["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in values["content-security-policy"]
