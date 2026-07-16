from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECRET_KEY_NAMES = (
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "CRICKOPS_COOKIE_SECRET",
    "CRICKOPS_ENCRYPTION_SECRET",
)
SECRET_FIXTURE_VALUES = (
    "postgresql://leak-user:leak-password@db.example/leak",
    "sk-frontend-leak-fixture",
    "cookie-secret-frontend-leak-fixture",
    "encryption-secret-frontend-leak-fixture",
)


def test_frontend_public_inputs_contain_no_server_secret_names_or_values() -> None:
    frontend_inputs = [
        ROOT / "apps" / "web" / "lib" / "env.ts",
        ROOT / ".env.example",
    ]
    public_build_fixture = (
        '{"NEXT_PUBLIC_API_BASE_URL":"/api/v1",'
        '"NEXT_PUBLIC_BUILD_SHA":"abcdef1"}'
    )
    scanned_text = public_build_fixture + "".join(
        path.read_text(encoding="utf-8") for path in frontend_inputs
    )

    for secret_name in SECRET_KEY_NAMES:
        assert not re.search(rf"NEXT_PUBLIC_{re.escape(secret_name)}", scanned_text)
    for secret_value in SECRET_FIXTURE_VALUES:
        assert secret_value not in scanned_text


def test_secret_scanner_configuration_covers_source_and_build_artifacts() -> None:
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    public_artifact_rule = next(
        rule
        for rule in config["rules"]
        if rule["id"] == "crickops-server-secret-in-public-artifact"
    )

    for artifact in ("apps/web/.next", "apps/web/public", "apps/web/out"):
        assert re.search(public_artifact_rule["path"], f"{artifact}/bundle.js")


def test_local_environment_files_are_ignored_but_example_is_tracked() -> None:
    ignore_patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in ignore_patterns
    assert ".env.*" in ignore_patterns
    assert "!.env.example" in ignore_patterns
