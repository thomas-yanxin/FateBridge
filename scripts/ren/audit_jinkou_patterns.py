"""Compare the 64 scanned headings against their literal four-position rows.

No expected pattern label or position is produced by FateBridge. Semantic
recognition and historical day/hour reconstruction are different comparisons.
All mismatches and unevaluated definitions remain in the denominator.
The existing manifest identity is pinned independently of its file digests.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_patterns_v1"
REFERENCE_FREEZE_SHA256 = (
    "a0baa38a704fb6b2ad015cafb4a79d54f43fc3f39525d0faef11d4594ab81961"
)
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
ELEMENTS = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
PHASES = dict(zip(BRANCHES, "水土木木土火火土金金土水"))
GOD_NAMES = {"天乙": "贵人", "腾蛇": "螣蛇"}
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/output_ren_patterns.py",
    "src/fatebridge/core/output_chinese.py",
    "scripts/ren/audit_jinkou_patterns.py",
)


def implementation_hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in IMPLEMENTATION
    }


def load_reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != REFERENCE_FREEZE_SHA256
    ):
        raise ValueError("Independent reference manifest identity changed")
    freeze = json.loads((corpus / "freeze.json").read_text())
    names = {"cases.json", "online-inventory.json", "page-map.json", "source-pages.pdf"}
    if set(freeze["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Independent source file inventory changed")
    for name, sha in freeze["files"].items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f"Independent reference changed: {name}")
    data: dict[str, Any] = json.loads((corpus / "cases.json").read_text())
    if len(data["cases"]) != 64 or len({c["id"] for c in data["cases"]}) != 64:
        raise ValueError("64 scanned source entries required")
    return data


def literal_rows(
    case: dict[str, Any], inherent: dict[str, str]
) -> list[dict[str, Any]]:
    """Build literal source inputs, not expected engine outputs.

    Auxiliary stems/empty flags use frozen v1 rules. Two absent day labels
    use an explicitly symbolic placeholder only for day-independent checks.
    These rows are never presented as a reconstructed historical date.
    """
    day = case["day"] or "甲子"
    cycle = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]
    index = cycle.index(day)
    empty = {
        BRANCHES[(index // 10 * 10 + 10) % 12],
        BRANCHES[(index // 10 * 10 + 11) % 12],
    }
    # Frozen v1: 子午水空、寅申金空. Xun ordinals are 子戌申午辰寅,
    # not ordinary branch ordinals; 戌/辰 must not receive 金空.
    empty_phase = {"甲子": "水", "甲午": "水", "甲寅": "金", "甲申": "金"}.get(
        cycle[index // 10 * 10]
    )
    ren, god_name, general, ground = case["positions"]
    contents = [ren, inherent[GOD_NAMES.get(god_name, god_name)][1], general, ground]
    start = (index % 10 % 5) * 2
    return [
        dict(
            label=label,
            content=value,
            element=ELEMENTS[value] if i == 0 else PHASES[value],
            dun_stem=(
                STEMS[(start + BRANCHES.index(value)) % 10] if i in (1, 2) else None
            ),
            xun_kong=i > 0 and value in empty,
            si_da_kong=(ELEMENTS[value] if i == 0 else PHASES[value]) == empty_phase,
        )
        for i, (label, value) in enumerate(
            zip(("人元", "贵神", "将神", "地分"), contents)
        )
    ]


def audit() -> dict[str, Any]:
    source = load_reference()
    before = implementation_hashes()
    spec = importlib.util.spec_from_file_location(
        "ren_v1_for_patterns", ROOT / "scripts/ren/audit_ren_classical.py"
    )
    assert spec and spec.loader
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    old = prior.load_frozen_corpus()
    # Import production only after independent references and their hashes.
    from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns

    semantics, reconstructions = [], []
    for case in source["cases"]:
        rows = literal_rows(case, old["rules"]["inherent"])
        board = structural_patterns(rows, day_ganzhi=case["day"] or "甲子")
        ids = {p["id"] for p in board["matched"]}
        unresolved = {p["id"] for p in board["unresolved"]}
        verdict = next(p for p in board["evaluations"] if p["id"] == case["id"])
        semantics.append(
            dict(
                id=case["id"],
                name=case["name"],
                source_page=case["original_pdf_page"],
                literal_positions=case["positions"],
                status=(
                    "unevaluated_definition"
                    if case["id"] in unresolved
                    else (
                        "matched"
                        if case["id"] in ids
                        else "definition_example_disagreement"
                    )
                ),
                matched=verdict["matched"],
            )
        )
        if case["day"] is None:
            reconstructions.append(
                dict(id=case["id"], status="missing_source_day", matched=None)
            )
            continue
        board = prior.observe_jinkou(
            dict(
                day=case["day"],
                hour=case["hour"],
                ground=case["positions"][3],
                month=BRANCHES[(case["lunar_month"] + 1) % 12],
                general=BRANCHES[(12 - case["lunar_month"]) % 12],
            )
        )
        actual = [
            board["rows"][0]["content"],
            board["overview"]["guishen"]["name"],
            board["rows"][2]["content"],
            board["rows"][3]["content"],
        ]
        reconstructions.append(
            dict(
                id=case["id"],
                status="compared_symbolic_month_general",
                actual=actual,
                expected=case["positions"],
                matched=actual
                == [
                    case["positions"][0],
                    GOD_NAMES.get(case["positions"][1], case["positions"][1]),
                    *case["positions"][2:],
                ],
                raw_name_spelling_matched=actual == case["positions"],
            )
        )
    matches = sum(c["matched"] is True for c in semantics)
    after = implementation_hashes()
    if before != after:
        raise ValueError("Implementation changed during pattern audit")
    return dict(
        implementation_sha256=after,
        reference_sha256=hashlib.sha256(
            (CORPUS / "freeze.json").read_bytes()
        ).hexdigest(),
        source_files=source["source_files"],
        reconstruction_name_normalization=GOD_NAMES,
        corpus_case_count=64,
        semantic_checks=semantics,
        semantic_status_counts={
            "matched": matches,
            "not_matched": sum(c["matched"] is False for c in semantics),
            "unresolved": sum(c["matched"] is None for c in semantics),
        },
        matched_semantic_cases=matches,
        unevaluated_definitions=sum(
            c["status"] == "unevaluated_definition" for c in semantics
        ),
        semantic_failures=[
            c for c in semantics if c["status"] == "definition_example_disagreement"
        ],
        source_day_reconstructions=reconstructions,
        matched_source_day_cases=sum(c["matched"] is True for c in reconstructions),
        reconstruction_status_counts={
            "matched": sum(c["matched"] is True for c in reconstructions),
            "not_matched": sum(c["matched"] is False for c in reconstructions),
            "unavailable": sum(c["matched"] is None for c in reconstructions),
        },
        reconstruction_scope="Source lunar month mapped to its stated month general, not an invented Gregorian event; actual 中气/timezone/true-solar boundaries tested elsewhere. Default 卯至申昼 convention cannot authenticate all original daylight cases.",
        classical_acceptance_passed=all(
            c["matched"] is True for c in semantics + reconstructions
        ),
        goal_complete=False,
        incomplete_requirements=[
            "Six pattern definitions unresolved",
            "Source definition/example disagreements need textual adjudication",
            "No adjudicated complete strength/polarity/use precedence",
            "No full-domain calendar or real-model interpretation acceptance in this audit",
        ],
    )
