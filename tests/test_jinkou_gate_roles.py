"""A 月将/贵神 role correction must generalize beyond one printed example."""

import asyncio
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jinkou_gate_audit", ROOT / "scripts/audit_jinkou_gate_roles.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_literal_roles_and_entire_synthetic_space_keep_full_corpus_denominators():
    report = AUDIT.audit()
    assert report["literal_structure_count"] == 2
    assert all(r["matched"] for r in report["literal_structure_checks"])
    assert report["synthetic_role_tuple_count"] == 1728
    assert report["synthetic_predicate_comparison_count"] == 3456
    assert report["synthetic_matches"] == {"P63": 12, "P64": 12}
    assert not report["synthetic_failures"]
    assert report["old_p64_formula_synthetic_false_positives"] == 11
    assert report["old_p64_formula_synthetic_false_negatives"] == 11
    full = report["prior_64_case_comparison"]
    assert full["semantic_status_counts"] == {
        "matched": 54,
        "not_matched": 4,
        "unresolved": 6,
    }
    assert full["reconstruction_status_counts"] == {
        "matched": 46,
        "not_matched": 16,
        "unavailable": 2,
    }
    assert {r["id"] for r in full["semantic_failures"]} == {"P03", "P04", "P05", "P25"}
    assert report["selected_role_checks_passed"]
    assert not report["classical_acceptance_passed"] and not report["goal_complete"]


@pytest.mark.parametrize(
    "god,general,ground,p63,p64",
    [
        ("辰", "戌", "辰", False, True),
        ("戌", "子", "辰", False, False),
        ("辰", "戌", "戌", True, False),
        ("亥", "辰", "戌", False, False),
    ],
)
def test_god_and_general_are_not_interchangeable(god, general, ground, p63, p64):
    result = structural_patterns(
        AUDIT.synthetic_rows(god, general, ground), day_ganzhi="乙卯"
    )
    ledger = {r["id"]: r for r in result["evaluations"]}
    assert ledger["P63"]["matched"] is p63 and ledger["P64"]["matched"] is p64
    assert "将神" in ledger["P64"]["condition"]
    if p64:
        item = next(p for p in result["matched"] if p["id"] == "P64")
        assert "第三位将神戌" in item["reading"]
        assert item["original_pdf_page"] == 123


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_new_collation_cannot_overwrite_or_hide_the_original_reference(
    tmp_path, change
):
    corpus = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "reference.json"
    if change == "edit":
        data = json.loads(p.read_text())
        data["synthetic_rule"]["P64"]["position"] = "贵神"
        p.write_text(json.dumps(data))
    elif change == "missing":
        p.unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen gate-role"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("hour,expected", [(14, True), (12, False)])
@pytest.mark.parametrize("project", [False, True])
def test_actual_four_positions_and_snapshot_agree_across_three_surfaces(
    hour, expected, project, rest, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    payload = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=10,
        analysis_hour=hour,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        di_fen="辰",
        selected_sections=["六十四课钤结构"],
    )
    # Full paths stay in one returned calculation; no re-computation for text.
    fields = ["jinkou.rows", "jinkou.patterns", "jinkou.ruleset"]
    params, flags, options = (
        [("response_char_limit", "0")],
        ["--response-char-limit", "0"],
        {},
    )
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        board = body["jinkou"]
        assert board["rows"][1]["content"] == "卯"
        assert board["rows"][2]["content"] == ("戌" if hour == 14 else "亥")
        assert board["rows"][3]["content"] == "辰"
        verdict = next(e for e in board["patterns"]["evaluations"] if e["id"] == "P64")
        assert verdict["matched"] is expected
        assert ("P64" in {p["id"] for p in board["patterns"]["matched"]}) is expected
        assert board["ruleset"]["version"] == "1.16.0"
        if not project:
            assert ("天门入地户课（地击卦）" in body["snapshot_text"]) is expected
            exported = next(
                s
                for s in body["snapshot_export"]["sections"]
                if s["title"] == "六十四课钤结构"
            )
            assert exported["included"]
            assert ("天门入地户课（地击卦）" in exported["content"]) is expected
