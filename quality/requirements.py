from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

IDENTIFIER = re.compile(r"\b([A-Z]+)-(\d{3})\b")
RANGE = re.compile(r"([A-Z]+)-(\d{3})\s*[–-]\s*([A-Z]+)-(\d{3})")
TASK = re.compile(r"\*\*TASK-(\d{3})\b")

EVIDENCE_BY_FAMILY = {
    "PROB": "../../tests/e2e/hero.spec.ts",
    "PERSONA": "../../tests/e2e/hero.spec.ts",
    "JTBD": "../../tests/e2e/hero.spec.ts",
    "JOURNEY": "../../tests/e2e/hero.spec.ts",
    "FR": "../../apps/api/tests/api/test_operations_contract.py",
    "SCHED": "../../apps/api/tests/scheduling/test_model.py",
    "WEATHER": "../../apps/api/tests/weather/test_risk.py",
    "AGENT": "../../apps/api/tests/agents/test_core_specialists.py",
    "RECOVERY": "../../apps/api/tests/scheduling/test_repair.py",
    "FAIR": "../../apps/api/tests/fairness/test_metrics.py",
    "APPROVAL": "../../apps/api/tests/approvals/test_approval_service.py",
    "UX": "../../tests/e2e/hero.spec.ts",
    "ACCESS": "../../tests/e2e/accessibility.spec.ts",
    "NFR": "hero-performance-gate.md",
    "SEC": "../../apps/api/tests/security/test_security_boundaries.py",
    "DATA": "../../apps/api/tests/persistence/test_repository.py",
    "OBS": "../../apps/api/tests/observability/test_observability.py",
    "FAIL": "../../apps/api/tests/api/test_operations_contract.py",
    "AC": "../../evals/run.py",
    "METRIC": "../../evals/run.py",
    "DEPLOY": "vercel-railway-session-spike.md",
}


@dataclass(frozen=True)
class MatrixAudit:
    missing: tuple[str, ...]
    duplicates: tuple[str, ...]
    unexpected: tuple[str, ...]


def _sort_key(identifier: str) -> tuple[str, int]:
    family, number = identifier.split("-", 1)
    return family, int(number)


def expand_identifiers(text: str) -> set[str]:
    expanded = {match.group(0) for match in IDENTIFIER.finditer(text)}
    for match in RANGE.finditer(text):
        start_family, start, end_family, end = match.groups()
        if start_family != end_family:
            raise ValueError(f"cross-family requirement range is invalid: {match.group(0)}")
        expanded.update(
            f"{start_family}-{number:03d}" for number in range(int(start), int(end) + 1)
        )
    return expanded


def v1_prd_identifiers(path: Path) -> set[str]:
    identifiers: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not IDENTIFIER.fullmatch(cells[0]):
            continue
        release = cells[1] if len(cells) > 1 else ""
        if release in {"Optional", "Future"}:
            continue
        identifiers.add(cells[0])
    return identifiers


def checklist_owners(path: Path) -> dict[str, tuple[str, ...]]:
    owners: dict[str, set[str]] = defaultdict(set)
    current_task: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        task_match = TASK.search(line)
        if task_match:
            current_task = f"TASK-{task_match.group(1)}"
        if current_task and "**Requirements:**" in line:
            for identifier in expand_identifiers(line):
                owners[identifier].add(current_task)
    return {identifier: tuple(sorted(tasks)) for identifier, tasks in owners.items()}


def render_matrix(prd_path: Path, checklist_path: Path) -> str:
    required = v1_prd_identifiers(prd_path)
    owners = checklist_owners(checklist_path)
    lines = [
        "# Version 1 requirement evidence matrix",
        "",
        "Generated and audited by `python -m quality.requirements --write`. Each Version 1 "
        "PRD identifier appears exactly once; Optional and Future identifiers are excluded.",
        "",
        "| Requirement | Implementation ownership | Primary automated evidence |",
        "|---|---|---|",
    ]
    for identifier in sorted(required, key=_sort_key):
        family = identifier.split("-", 1)[0]
        tasks = ", ".join(owners.get(identifier, ("TASK-054 contract audit",)))
        evidence = EVIDENCE_BY_FAMILY[family]
        lines.append(f"| {identifier} | {tasks} | [`{evidence}`]({evidence}) |")
    lines.extend(
        (
            "",
            "## Validation boundary",
            "",
            "This matrix proves identifier ownership and primary evidence coverage. "
            "TASK-055–TASK-058 repeat deployment-specific contracts against the final public "
            "environment; their live "
            "reports supplement rather than replace the automated evidence linked above.",
            "",
        )
    )
    return "\n".join(lines)


def audit_matrix(path: Path, required: set[str]) -> MatrixAudit:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and IDENTIFIER.fullmatch(cells[0]):
                rows.append(cells[0])
    counts = Counter(rows)
    found = set(rows)
    return MatrixAudit(
        missing=tuple(sorted(required - found, key=_sort_key)),
        duplicates=tuple(
            sorted((item for item, count in counts.items() if count > 1), key=_sort_key)
        ),
        unexpected=tuple(sorted(found - required, key=_sort_key)),
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate and audit the V1 requirement matrix")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "docs" / "evidence" / "requirement-matrix.md"
    if args.write:
        output.write_text(render_matrix(root / "prd.md", root / "checklist.md"), encoding="utf-8")
    required = v1_prd_identifiers(root / "prd.md")
    result = audit_matrix(output, required)
    print(
        f"required={len(required)} missing={len(result.missing)} "
        f"duplicates={len(result.duplicates)} unexpected={len(result.unexpected)}"
    )
    return 0 if result == MatrixAudit((), (), ()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
