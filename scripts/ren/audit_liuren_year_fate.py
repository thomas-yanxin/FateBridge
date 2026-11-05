"""Check literal 年命 tables and one diagram; do not certify a whole book."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fatebridge.core.metaphysics.common import MetaphysicsSeed

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_year_fate_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/liureng_year_fate.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_liuren_year_fate.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_liuren_year_fate.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen year-fate inventory changed")
    for name, digest in manifest["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError(f"Frozen year-fate source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    return result


def symbolic_seed() -> MetaphysicsSeed:
    from fatebridge.core.metaphysics.common import MetaphysicsSeed

    # The original gives cyclical inputs only. This civil date supplies a known
    # 甲子 lunar year for age arithmetic, not a claimed reconstruction of 占日.
    moment = datetime(1984, 6, 1, 6)
    return MetaphysicsSeed(
        input_datetime=moment,
        corrected_datetime=moment,
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={
            "year": ("甲", "子"),
            "month": ("丙", "寅"),
            "day": ("甲", "辰"),
            "hour": ("丁", "卯"),
        },
        calendar_context={"current_solar_term": {"name": "雨水"}},
    )


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.liureng import (
        build_liureng_board,
        build_liureng_runyear,
    )
    from fatebridge.core.metaphysics.liureng_year_fate import (
        build_year_fate,
        natal_year_ganzhi,
    )

    seed = symbolic_seed()
    table_checks = []
    for gender, table in ref["runyear_tables"].items():
        for age, expected in enumerate(table, 1):
            year = 1984 - age + 1
            result = build_liureng_runyear(seed, gender, year, birth_lunar_year=year)
            actual = result["ganzhi"]
            table_checks.append(
                dict(
                    gender=gender,
                    age=age,
                    expected=expected,
                    actual=actual,
                    matched=actual == expected and result["age"] == age,
                )
            )
    natal_checks = []
    for year, row in zip((1984, 1985), ref["natal_examples"]):
        actual = natal_year_ganzhi(year)
        natal_checks.append(
            dict(
                birth_lunar_year=year,
                **row,
                actual=actual,
                matched=actual == row["natal_ganzhi"],
            )
        )
    board = build_liureng_board(
        seed, month_general_override="亥", guiren_profile="tanyuan_xieji_v1"
    )
    positions = []
    for row in ref["diagram"]["placements"]:
        gender = row["gender"] or "未知"
        runyear = build_liureng_runyear(seed, gender, 1941, birth_lunar_year=1941)
        facts = build_year_fate(
            board,
            day_ganzhi="甲辰",
            birth_lunar_year=1941,
            runyear_ganzhi=runyear["ganzhi"],
            runyear_reason=runyear.get("reason"),
        )
        actual = facts[row["kind"]]
        expected = {
            k: row[k] for k in ("subject_ganzhi", "earth_branch", "sky_branch", "god")
        }
        positions.append(
            dict(
                kind=row["kind"],
                gender=row["gender"],
                expected=expected,
                actual=actual,
                matched=all(actual[k] == v for k, v in expected.items()),
            )
        )
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    checks = table_checks + natal_checks + positions
    return dict(
        audit_id="liuren_year_fate_v1",
        literal_runyear_checks=table_checks,
        literal_runyear_count=len(table_checks),
        literal_runyear_matches=sum(c["matched"] for c in table_checks),
        literal_natal_definition_checks=natal_checks,
        source_diagram_count=1,
        source_diagram_position_checks=positions,
        source_diagram_position_matches=sum(c["matched"] for c in positions),
        failures=[c for c in checks if not c["matched"]],
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_excerpt_checks_passed=unchanged and all(c["matched"] for c in checks),
        classical_acceptance_passed=False,
        full_supported_calendar_domain_certified=False,
        goal_complete=False,
        new_real_world_outcomes=0,
        model_invocations=0,
        scope=ref["scope"],
        convention_notes=ref["convention_notes"],
    )
