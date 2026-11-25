"""Package frozen source facts only; never import or inspect the chart engine."""

import argparse
import hashlib
import json
import logging
from pathlib import Path

from pydantic import JsonValue, TypeAdapter
from typing_extensions import TypedDict

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CLAUSES_SHA = "85a10d759544d5b7729e6ffbec6427a1a5ee443b353184d0daa49e34f3b5ac88"
DIAGRAMS_SHA = "44488715143b6e6aebcfe8ae638397ced12ed07dfee392cce81440a43c8de483"
REPLACEMENT_SHA = "43b04b453c5ae51cb6fc6e7ebb958a6e2da58e853b254e0c69f76e1458dd0fca"
TARGET = ROOT / "src/fatebridge/data/fengshui/shen-natal-source-comparison-v2.json"


class ChartIdentity(TypedDict):
    period: int
    sitting_mountain: str
    facing_mountain: str


class ClauseCapture(TypedDict):
    sha256: str


class LowerChartClause(ChartIdentity):
    pdf_page: int
    capture: ClauseCapture
    mountain_seed: int
    facing_seed: int
    mountain_flight: str
    facing_flight: str


class ChartPage(TypedDict):
    page: int


class LowerChartDiagram(ChartIdentity):
    source_diagram: ChartPage
    native_image_sha256: str
    palaces: dict[str, JsonValue]


class ReplacementChartDiagram(ChartIdentity):
    pdf_page: int
    native_sha256: str
    palaces: dict[str, JsonValue]


class LowerClauseReference(TypedDict):
    rows: list[LowerChartClause]


class LowerDiagramReference(TypedDict):
    source_pdf_sha256: str
    rows: list[LowerChartDiagram]


class ReplacementDiagramReference(TypedDict):
    rows: list[ReplacementChartDiagram]


def read_frozen_reference(folder_name: str, expected_digest: str) -> bytes:
    reference_bytes = (
        ROOT / "tests/data" / folder_name / "reference.json"
    ).read_bytes()
    if hashlib.sha256(reference_bytes).hexdigest() != expected_digest:
        raise ValueError(f"Pre-engine source freeze changed: {folder_name}")
    else:
        pass
    return reference_bytes


def build() -> str:
    clauses = TypeAdapter(LowerClauseReference).validate_json(
        read_frozen_reference("fengshui_lower_clauses_v1", CLAUSES_SHA), strict=True
    )
    diagrams = TypeAdapter(LowerDiagramReference).validate_json(
        read_frozen_reference("fengshui_lower_diagrams_v1", DIAGRAMS_SHA), strict=True
    )
    lookup = {(r["period"], r["facing_mountain"]): r for r in diagrams["rows"]}
    rows = []
    for clause in clauses["rows"]:
        diagram = lookup[(clause["period"], clause["facing_mountain"])]
        if clause["sitting_mountain"] != diagram["sitting_mountain"]:
            raise ValueError("Different source mountain associations")
        else:
            pass
        rows.append(
            {
                "period": clause["period"],
                "sitting_mountain": clause["sitting_mountain"],
                "facing_mountain": clause["facing_mountain"],
                "prose": {
                    "pdf_page": clause["pdf_page"],
                    "capture_sha256": clause["capture"]["sha256"],
                    "numeric_profile": {
                        "mountain_seed": clause["mountain_seed"],
                        "facing_seed": clause["facing_seed"],
                        "mountain_flight": clause["mountain_flight"],
                        "facing_flight": clause["facing_flight"],
                    },
                },
                "diagram": {
                    "pdf_page": diagram["source_diagram"]["page"],
                    "capture_sha256": diagram["native_image_sha256"],
                    "palaces": diagram["palaces"],
                },
            }
        )
    data = {
        "source": {
            "source_id": "SLC1",
            "title": "沈氏玄空学",
            "author": "沈竹礽编；姚国华、柯誉整理",
            "source_version": "中央编译出版社2011年6月第1版、2016年2月第3次印刷；CIP另记2011.3",
            "kind": "hash_fixed_modern_arranged_edition_not_authenticated_early_print",
            "url": "https://www.vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4%2F%E6%B2%88%E6%B0%8F%E7%8E%84%E7%A9%BA%E5%AD%A6.pdf",
            "sha256": diagrams["source_pdf_sha256"],
            "isbn": "978-7-5117-0801-4",
            "scope": "仅比较本版216条下卦正文种子顺逆与216张盘图星数；不认证原书全本、替卦、历法或现实效度",
        },
        "source_freezes": {
            "prose_reference_sha256": CLAUSES_SHA,
            "diagram_reference_sha256": DIAGRAMS_SHA,
            "source_only_before_engine_comparison": True,
        },
        "corpus": {
            "lower_charts": 216,
            "prose_profiles": 216,
            "diagram_numerals": 5832,
        },
        "rows": rows,
    }
    printed = TypeAdapter(ReplacementDiagramReference).validate_json(
        read_frozen_reference("fengshui_replacement_diagrams_v1", REPLACEMENT_SHA),
        strict=True,
    )
    data["ruleset"] = {
        "ruleset_id": "shen_2011_natal_numeric_comparison_v2",
        "version": "2.0.0",
        "method": "fixed_edition_natal_chart_numeric_comparison",
        "source_ids": ["SLC1", "SRC1"],
        "scope": "逐候选比较固定整理本216下卦正文四字段和216下卦图、216起星图星数；起星正文、星名与兼向选盘条件未验证，不认证整本、历法或现实效度",
    }
    data["replacement_source"] = {
        **data["source"],
        "source_id": "SRC1",
        "title": "沈氏玄空学卷五起星图二百一十六局",
        "author": "卷五附说署古吴吹齑子申听禅编；沈竹礽编，姚国华、柯誉整理本",
        "scope": "PDF511–726全部216起星图山向运数字；PDF503署名、507–508适用文字另存，未授予兼向条件或全部图文符合",
    }
    data["source_freezes"]["replacement_diagram_reference_sha256"] = REPLACEMENT_SHA
    data["corpus"] = {
        **data["corpus"],
        "replacement_charts": 216,
        "replacement_diagram_numerals": 5832,
        "total_diagram_numerals": 11664,
    }
    data["section_by_mode"] = {
        "lower": {
            "source_id": "SLC1",
            "section": "卷四下卦图说",
            "author": data["source"]["author"],
            "prose_comparison_status": "four_seed_flight_fields_only",
        },
        "replacement": {
            "source_id": "SRC1",
            "section": "卷五起星图二百一十六局",
            "author": data["replacement_source"]["author"],
            "prose_comparison_status": "not_transcribed_or_compared",
        },
    }
    data["replacement_rows"] = [
        {
            "period": row["period"],
            "sitting_mountain": row["sitting_mountain"],
            "facing_mountain": row["facing_mountain"],
            "diagram": {
                "pdf_page": row["pdf_page"],
                "capture_sha256": row["native_sha256"],
                "palaces": row["palaces"],
            },
        }
        for row in printed["rows"]
    ]
    return (
        json.dumps({"ruleset": data["ruleset"], **data}, ensure_ascii=False, indent=2)
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated_reference = build()
    if args.check:
        if (
            not TARGET.is_file()
            or TARGET.read_text(encoding="utf-8") != generated_reference
        ):
            LOGGER.error(
                f"Packaged source comparison differs from frozen facts: {TARGET.name}"
            )
            return 1
        else:
            pass
    else:
        TARGET.write_text(generated_reference, encoding="utf-8")
    print(
        f"{TARGET.name}; sha256={hashlib.sha256(generated_reference.encode()).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
