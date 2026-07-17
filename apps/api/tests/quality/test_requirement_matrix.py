from __future__ import annotations

from pathlib import Path

from quality.requirements import audit_matrix, expand_identifiers, v1_prd_identifiers

ROOT = Path(__file__).resolve().parents[4]


def test_identifier_ranges_expand_without_losing_single_ids() -> None:
    assert expand_identifiers("FR-001–FR-003, SEC-002") == {
        "FR-001",
        "FR-002",
        "FR-003",
        "SEC-002",
    }


def test_requirement_matrix_has_exactly_one_row_for_every_v1_prd_identifier() -> None:
    required = v1_prd_identifiers(ROOT / "prd.md")
    result = audit_matrix(ROOT / "docs" / "evidence" / "requirement-matrix.md", required)

    assert len(required) > 200
    assert result.missing == ()
    assert result.duplicates == ()
    assert result.unexpected == ()
