import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class ScaffoldContractTest(unittest.TestCase):
    def test_root_exposes_required_javascript_quality_commands(self) -> None:
        package_path = ROOT / "package.json"
        self.assertTrue(package_path.is_file(), "root package.json must exist")
        package = json.loads(package_path.read_text(encoding="utf-8"))
        web_package = json.loads(
            (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
        )

        self.assertEqual(package["scripts"]["lint"], "pnpm --filter @crickops/web lint")
        self.assertEqual(package["scripts"]["test"], "pnpm --filter @crickops/web test")
        self.assertTrue(package["packageManager"].startswith("pnpm@"))
        self.assertEqual(web_package["scripts"]["lint"], "eslint . --max-warnings=0")

    def test_repository_defines_formatter_rules(self) -> None:
        editorconfig_path = ROOT / ".editorconfig"
        self.assertTrue(editorconfig_path.is_file(), "root .editorconfig must exist")
        editorconfig = editorconfig_path.read_text(encoding="utf-8")

        self.assertIn("charset = utf-8", editorconfig)
        self.assertIn("end_of_line = lf", editorconfig)
        self.assertIn("insert_final_newline = true", editorconfig)
        self.assertIn("trim_trailing_whitespace = true", editorconfig)
        self.assertIn(
            "[*.{js,jsx,ts,tsx,mjs,cjs,json,jsonc,css,scss,yml,yaml}]\n"
            "indent_style = space\n"
            "indent_size = 2",
            editorconfig,
        )
        self.assertIn("[*.py]\nindent_style = space\nindent_size = 4", editorconfig)

    def test_api_declares_required_python_quality_tools(self) -> None:
        pyproject_path = ROOT / "apps" / "api" / "pyproject.toml"
        self.assertTrue(pyproject_path.is_file(), "API pyproject.toml must exist")
        pyproject = tomllib.loads(
            pyproject_path.read_text(encoding="utf-8")
        )

        development_dependencies = pyproject["dependency-groups"]["dev"]
        self.assertTrue(any(item.startswith("pytest") for item in development_dependencies))
        self.assertTrue(any(item.startswith("ruff") for item in development_dependencies))

    def test_root_installs_api_workspace_dependencies(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn("crickops-api", pyproject["project"]["dependencies"])
        self.assertEqual(
            pyproject["tool"]["uv"]["sources"]["crickops-api"],
            {"workspace": True},
        )

    def test_workspace_contains_web_and_api_packages(self) -> None:
        workspace_path = ROOT / "pnpm-workspace.yaml"
        self.assertTrue(workspace_path.is_file(), "pnpm workspace file must exist")
        workspace = workspace_path.read_text(encoding="utf-8")

        self.assertIn("apps/*", workspace)
        self.assertTrue((ROOT / "apps" / "web" / "package.json").is_file())
        self.assertTrue((ROOT / "apps" / "api" / "app" / "main.py").is_file())


if __name__ == "__main__":
    unittest.main()
