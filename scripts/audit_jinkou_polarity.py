"""Replay formal polarity rules and reachable symbolic courses separately.

No civil calendar reconstruction, comprehensive use selection, or real-world
prediction is certified. The independent reference predates this auditor.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_polarity_reachability_v1"
PIN = "1d022b836257b7283b504e1a81e2283e65ddef1012a7689219204afaa7bda183"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != PIN:
        raise ValueError("Frozen polarity reference identity changed")
    manifest = json.loads((corpus / "freeze.json").read_text())
    expected = {
        "readings.json",
        "reference.json",
        "generate_reference.py",
        *(f"page-{page:03}.jpg" for page in range(41, 47)),
    }
    if set(manifest["files"]) != expected or {
        p.name for p in corpus.iterdir() if p.name != "__pycache__"
    } != expected | {"freeze.json"}:
        raise ValueError("Frozen polarity file inventory changed")
    for name, digest in manifest["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError("Frozen polarity reference bytes changed: " + name)
    readings = json.loads((corpus / "readings.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_month_building_v1/source.pdf")
        != readings["source_sha256"]
        or sha(ROOT / "tests/fixtures/ren_classical_v1/freeze.json")
        != readings["annotation"]["reused_old_table_pin"]
    ):
        raise ValueError("Polarity original source identity changed")
    from scripts.audit_ren_classical import load_frozen_corpus

    load_frozen_corpus()
    spec = importlib.util.spec_from_file_location(
        "independent_polarity_reference", corpus / "generate_reference.py"
    )
    assert spec and spec.loader
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    answer = json.loads((corpus / "reference.json").read_text())
    if generator.build(readings) != answer or len(answer["cases"]) != 17280:
        raise ValueError("Independent polarity reference cannot be reproduced")
    return dict(readings=readings, reference=answer)


def observe(case: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from scripts.audit_ren_classical import make_seed

    seed = make_seed(dict(day=case["day"], hour="子", month="寅"))
    return build_jinkou_board(
        seed,
        {"month_general": {"branch": case["general"]}},
        di_fen=case["ground"],
        is_diurnal_override=case["is_diurnal"],
    )


def selected_facts(board: dict[str, Any]) -> dict[str, Any]:
    return dict(
        contents=[r["content"] for r in board["rows"]],
        elements=[r["element"] for r in board["rows"]],
        god=board["overview"]["guishen"]["name"],
        intrinsic_ganzhi=board["rows"][1]["intrinsic_ganzhi"],
        dun_stems=[r["dun_stem"] for r in board["rows"]],
        mask="".join(r["polarity"] for r in board["rows"]),
        pattern=board["overview"]["board_style_detail"],
        use=board["overview"]["use_position"],
        is_use=[r["is_use"] for r in board["rows"]],
        xun_kong=[r["xun_kong"] for r in board["rows"]],
        si_da_kong=[r["si_da_kong"] for r in board["rows"]],
        month_break=[r["month_break"] for r in board["rows"]],
        conditions={
            k: board["use_evidence"][k]
            for k in (
                "polarity_position",
                "controlled_by",
                "xun_kong",
                "si_da_kong",
                "month_break",
                "comprehensive_position",
            )
        },
    )


def compare_case(
    case: dict[str, Any], board: dict[str, Any], *, readings: dict[str, Any]
) -> dict[str, Any]:
    positions = ("人元", "贵神", "将神", "地分")
    selected = positions.index(case["use"])
    expected = {
        k: case[k]
        for k in (
            "contents",
            "god",
            "intrinsic_ganzhi",
            "dun_stems",
            "mask",
            "pattern",
            "use",
            "xun_kong",
            "si_da_kong",
            "month_break",
        )
    }
    expected["is_use"] = [p == case["use"] for p in positions]
    expected["elements"] = [readings["stem_elements"][case["contents"][0]]] + [
        readings["branch_elements"][v] for v in case["contents"][1:]
    ]
    expected["conditions"] = dict(
        polarity_position=case["use"],
        controlled_by=case["controlled_by"],
        xun_kong=case["xun_kong"][selected],
        si_da_kong=case["si_da_kong"][selected],
        month_break=case["month_break"][selected],
        comprehensive_position=None,
    )
    actual = selected_facts(board)

    # JSON bytes distinguish booleans, integers and null, unlike Python ==.
    def dump(value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    trace = [t for t in board["rule_trace"] if t["rule_id"] == "jinkou.polarity_use"]
    use_trace = [
        t for t in board["rule_trace"] if t["rule_id"] == "jinkou.use_conditions"
    ]
    traces_match = (
        len(trace) == len(use_trace) == 1
        and dump(trace[0]["result"])
        == dump(dict(pattern=case["pattern"], position=case["use"]))
        and dump(use_trace[0]["result"]) == dump(board["use_evidence"])
    )
    return dict(
        matched=dump(actual) == dump(expected) and traces_match,
        traces_match=traces_match,
        actual=actual,
        expected=expected,
    )


def audit() -> dict[str, Any]:
    data = reference()
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__).resolve(),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.metaphysics.jinkou import _jinkou_pick_use_position

    formal = []
    for mask, pattern, use in data["readings"]["formal_truth_table"]:
        rows = [
            dict(label=p, polarity=v)
            for p, v in zip(data["readings"]["positions"], mask)
        ]
        actual_use, _, actual_pattern = _jinkou_pick_use_position(rows)
        formal.append(
            dict(
                mask=mask,
                expected_use=use,
                actual_use=actual_use,
                expected_pattern=pattern,
                actual_pattern=actual_pattern,
                reachable=mask in data["reference"]["mask_counts"],
                matched=actual_use == use and actual_pattern == pattern,
            )
        )
    failures: list[dict[str, Any]] = []
    masks: Counter[str] = Counter()
    uses: Counter[str] = Counter()
    checked = 0
    mismatched_phase_same_polarity, different_polarity = 0, 0
    ledger = hashlib.sha256()
    for case in data["reference"]["cases"]:
        board = observe(case)
        result = compare_case(case, board, readings=data["readings"])
        if not result["matched"]:
            failures.append(dict(input=case, **result))
        actual = result["actual"]
        masks[actual["mask"]] += 1
        uses[actual["use"]] += 1
        ledger.update(
            (json.dumps(dict(input=case, **result), sort_keys=True) + "\n").encode()
        )
        god = board["rows"][1]
        stem = god["dun_stem"]
        readings = data["readings"]
        different_polarity += readings["stem_polarity"][stem] != god["polarity"]
        if readings["stem_elements"][stem] != god["element"]:
            mismatched_phase_same_polarity += (
                readings["stem_polarity"][stem] == god["polarity"]
            )
        checked += 1
    unchanged = before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not unchanged:
        raise ValueError("Source changed during polarity audit; repeat on fixed bytes")
    from scripts.audit_jinkou_strength import audit as strength_audit

    old = strength_audit()
    scope_passed = (
        checked == 17280
        and all(r["matched"] for r in formal)
        and not failures
        and dict(sorted(masks.items())) == data["reference"]["mask_counts"]
        and dict(sorted(uses.items())) == data["reference"]["use_counts"]
        and different_polarity == 0
    )
    return dict(
        reference_pin=PIN,
        formal_mask_count=len(formal),
        formal_rules=formal,
        symbolic_case_count=checked,
        mask_counts=dict(sorted(masks.items())),
        use_counts=dict(sorted(uses.items())),
        unreachable_masks=data["reference"]["unreachable_masks"],
        failures=failures,
        selected_fact_ledger_sha256=ledger.hexdigest(),
        god_dun_polarity_difference_count=different_polarity,
        god_dun_phase_different_but_polarity_same=mismatched_phase_same_polarity,
        polarity_scope_passed=scope_passed,
        source_scope=data["readings"]["scope"],
        original_scan_audit={
            k: old[k]
            for k in (
                "scan_case_count",
                "scan_matched_count",
                "older_online_matched_count",
                "scan_failures",
                "classical_acceptance_passed",
            )
        },
        implementation_sha256=before,
        implementation_unchanged=unchanged,
        calendar_validation="not_assessed_symbolic_inputs",
        comprehensive_use_adjudicated=False,
        final_use_void_predicate_adjudicated=False,
        classical_acceptance_passed=False,
        new_independent_real_events=0,
        new_model_processes=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    options = parser.parse_args()
    result = audit()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if options.output:
        with options.output.open("x") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")
    return (
        0
        if result["polarity_scope_passed"] and not options.require_full_conformance
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
