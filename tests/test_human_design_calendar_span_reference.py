"""Keep expanded external-reference failures and the original acceptance scope."""

import ast
import json
import shutil
from pathlib import Path

import pytest

from scripts import check_human_design_calendar_span as audit

ROOT = Path(__file__).resolve().parents[1]


def test_every_supported_year_has_both_predeclared_additional_seasons():
    plan, data = audit.reference(ROOT)
    assert len(plan["birth_epochs"]) == len(data["pairs"]) == 1200
    assert [r["label"] for r in plan["birth_epochs"]] == [
        f"{year:04d}-{month:02d}-01T12:00:00 TT"
        for year in range(1800, 2400)
        for month in (3, 9)
    ]
    original = json.loads(
        (ROOT / "tests/fixtures/human-design-astronomy-de440.json").read_text()
    )
    assert not (
        {r["personality"]["jd_tt"] for r in original["pairs"]}
        & {r["personality"]["jd_tt"] for r in data["pairs"]}
    )


@pytest.mark.parametrize(
    "change", ["remove_row", "replace_longitude", "raise_tolerance"]
)
def test_the_frozen_cohort_cannot_be_narrowed_or_made_easier(tmp_path, change):
    for name in audit.BINDINGS:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    if change == "raise_tolerance":
        path = tmp_path / "tests/fixtures/human-design-calendar-span-plan.json"
        value = json.loads(path.read_text())
        value["comparison_tolerance_arcseconds"] = 10.0
    else:
        path = tmp_path / "tests/fixtures/human-design-calendar-span-de440.json"
        value = json.loads(path.read_text())
        if change == "remove_row":
            value["pairs"].pop(0)
        else:
            value["pairs"][0]["design"]["positions"]["Uranus"]["longitude"] += 1.0
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Frozen calendar reference changed"):
        audit.reference(tmp_path)


def test_a_failed_position_is_kept_alongside_all_passing_rows(monkeypatch):
    # Four small synthetic positions test failure retention only; these never
    # enter the independent reference or the claimed external sample count.
    pairs = [
        {
            "label": str(i),
            **{
                side: {
                    "jd_tt": float(i * 2 + offset),
                    "positions": {"Uranus": {"longitude": 1.0}},
                }
                for side, offset in (("personality", 0), ("design", 1))
            },
        }
        for i in range(2)
    ]
    monkeypatch.setattr(
        audit,
        "reference",
        lambda root: ({"scope": "synthetic retention test"}, {"pairs": pairs}),
    )

    def positions(epoch, node_mode, backend):
        return {
            "Uranus": {
                "longitude": 1.0 + (3.0 / 3600 if epoch == 1.0 else 0.0),
                "ephemeris_model": backend,
                "return_flags": 258 if backend == "swieph" else 260,
            }
        }

    monkeypatch.setattr(audit, "positions_at_tt", positions)
    monkeypatch.setattr(
        audit,
        "solve_design_epoch_tt",
        lambda epoch, backend: {"solver": {"design_jd_tt": epoch + 1}},
    )
    result = audit.checks()
    assert result["status"] == "failed"
    assert result["complete_calendar_acceptance"] is False
    for backend in result["backends"].values():
        assert backend["position_count"] == 4
        assert backend["positions_matched"] == 3
        assert len(backend["position_failures"]) == 1
        assert backend["position_failures"][0]["jd_tt"] == 1.0


def test_finite_success_cannot_satisfy_full_calendar_acceptance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit,
        "checks",
        lambda: {
            "status": "additional_bounded_match",
            "complete_calendar_acceptance": False,
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check",
            "--require-full-acceptance",
            "--output",
            str(tmp_path / "report.json"),
        ],
    )
    assert audit.main() == 1


def test_reference_generator_has_no_fatebridge_or_swiss_imports():
    source = (ROOT / "scripts/gen_human_design_calendar_span_reference.py").read_text()
    imports = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(
        name.startswith(("fatebridge", "swisseph", "pyswisseph")) for name in imports
    )
