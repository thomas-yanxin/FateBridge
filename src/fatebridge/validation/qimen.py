"""Frozen facsimile comparison, including disagreements, for the Qimen audit."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import _qimen_build_palaces, _qimen_zhifu_zhishi
from fatebridge.core.qimen_evidence import SOURCE, STEM_PATTERNS, enrich_qimen_evidence
from fatebridge.core.qimen_profiles import GOD_PROFILES, star_season_state
from fatebridge.validation.claims import CalculationClaim


def audit_day_stem_collation(directory: Path) -> dict[str, Any]:
    """Keep preferred-source conflicts and supporting textual variants separate."""
    manifest = json.loads((directory / "sources-and-stems.json").read_text())
    if len(manifest["source_files"]) != 4 or {
        s["file"] for s in manifest["source_files"]
    } != {
        "../qimen_classical_v5/siku-pages-29-31-32.pdf",
        "tushu705-p127.jpg",
        "tushu705-p128.jpg",
        "commons-imageinfo.json",
    }:
        raise ValueError("日干校勘须保留全部影印页与来源元数据")
    if len(manifest["literal_definitions"]) != 3 or {
        d["rule_id"] for d in manifest["literal_definitions"]
    } != {"hidden_day_stem", "flying_day_stem", "hour_stem_block"}:
        raise ValueError("日干校勘须保留三条原文定义")
    for entry in manifest["source_files"]:
        path = (directory / entry["file"]).resolve()
        if not path.is_relative_to(directory.resolve().parent):
            raise ValueError("日干例局参考路径越出参考目录")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("日干例局参考文件指纹不一致")
    cases = manifest["cases"]
    required = {
        "vol2-yang5-renshen-geng-palace",
        "tushu705-fugan-renshen",
        "vol2-day-block-ji",
        "vol2-hour-block-jichou",
        "tushu705-feigan-day-jia-candidate",
        "tushu705-shige-yichou-variant",
    }
    if len(cases) != 6 or {c["id"] for c in cases} != required:
        raise ValueError("日干校勘须保留六项，包括原文分歧和未采纳候选")
    rows: list[dict[str, Any]] = []
    for case in cases:
        ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        leader = _qimen_zhifu_zhishi(case["hour"], ju, dun_type=case["dun"])
        palaces = _qimen_build_palaces(
            time_ganzhi=case["hour"],
            ju_text=ju,
            dun_type=case["dun"],
            current_term="冬至",
        )
        at = datetime(2026, 1, 1, 12)
        seed = MetaphysicsSeed(
            at,
            at,
            "Asia/Shanghai",
            None,
            False,
            0.0,
            {"month": ("丙", "寅")},
            {"current_solar_term": {"name": "冬至"}},
        )
        board = enrich_qimen_evidence(
            {
                "ju_text": ju,
                "palaces": palaces,
                "ju_method": "zhirun",
                "ju_term": "冬至",
                "day_ganzhi": case["day"],
                "time_ganzhi": case["hour"],
                "kongwang": "戌亥空",
            },
            seed=seed,
            leader=leader,
        )
        expected = case["expected"]
        kind = case["comparison_kind"]
        if kind == "palace_observation":
            actual = {
                "heaven_geng_palace": next(
                    p["trigram"] for p in palaces if "庚" in p["heaven_stems"]
                )
            }
        elif kind == "literal_stem_pattern":
            match = next(
                (p for p in board["patterns"] if p["name"] == expected["pattern"]), None
            )
            at_palace = next(
                (p for p in palaces if match and p["name"] == match["palace"]), None
            )
            actual = {
                "pattern": match["name"] if match else None,
                "palace": at_palace["trigram"] if at_palace else None,
                "heaven_stem": match["facts"]["heaven_stem"] if match else None,
                "earth_stem": match["facts"]["earth_stem"] if match else None,
            }
        elif kind == "unadopted_day_jia_candidate":
            day_context = board["stem_context"]["day"]
            candidate = next(
                c
                for c in day_context["candidates"]
                if c["policy"] == expected["candidate_policy"]
            )
            if candidate["adopted"] or day_context["adopted_candidate"] is not None:
                raise ValueError("未解决日甲候选不能因匹配单例而自动采纳")
            actual = {
                "candidate_policy": candidate["policy"],
                "flying_day_stem_palaces": candidate["candidate_matches"][
                    "flying_day_stem"
                ],
            }
        else:
            raise ValueError("日干校勘包含未知对照类型")
        differences = [
            {"field": k, "expected": v, "actual": actual[k]}
            for k, v in expected.items()
            if actual[k] != v
        ]
        status = (
            "source_disagreement"
            if differences
            else (
                "candidate_reproduced_not_adopted"
                if kind == "unadopted_day_jia_candidate"
                else "observations_match"
            )
        )
        rows.append(
            {
                "case_id": case["id"],
                "source_role": case["source_role"],
                "source_section": case["source_section"],
                "source_page": case["source_page"],
                "status": status,
                "differences": differences,
            }
        )
    preferred = [
        {"case_id": row["case_id"], **d}
        for row in rows
        if row["source_role"] == "preferred"
        for d in row["differences"]
    ]
    supporting = [
        {"case_id": row["case_id"], **d}
        for row in rows
        if row["source_role"] == "supporting"
        for d in row["differences"]
    ]
    return {
        "method_id": "qimen_day_stem_source_collation_v6",
        "case_count": len(rows),
        "matched_observation_count": sum(
            r["status"] == "observations_match" for r in rows
        ),
        "unadopted_candidate_reproduction_count": sum(
            r["status"] == "candidate_reproduced_not_adopted" for r in rows
        ),
        "preferred_source_disagreements": preferred,
        "supporting_source_disagreements": supporting,
        "rows": rows,
        "day_jia_rule_accepted": False,
        "supporting_transcription_proofread_status": "unproofread; selected scan words visually checked",
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }


def audit_head_dependent_examples(directory: Path) -> dict[str, Any]:
    """Replay six printed examples without conflating day Jia and hour xun Jia."""
    manifest = json.loads((directory / "sources-and-cases.json").read_text())
    for file_key, hash_key in [
        ("excerpt_file", "excerpt_sha256"),
        ("earlier_excerpt_file", "earlier_excerpt_sha256"),
    ]:
        source = (directory / manifest[file_key]).resolve()
        if not source.is_relative_to(directory.resolve().parent):
            raise ValueError("奇门旬首例局影印路径越出参考目录")
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest[hash_key]:
            raise ValueError("奇门旬首例局影印指纹不一致")
    cases = manifest["cases"]
    required = {
        ("阳遁", 9, "辛未", "飞鸟跌穴"),
        ("阳遁", 3, "丁卯", "飞鸟跌穴"),
        ("阳遁", 1, "丙寅", "青龙返首"),
        ("阳遁", 2, "壬申", "天乙伏宫格"),
        ("阳遁", 9, "庚午", "天乙飞宫格"),
        ("阴遁", 4, "丙寅", "大格"),
    }
    if (
        len(cases) != 6
        or {(c["dun"], c["ju"], c["hour"], c["name"]) for c in cases} != required
    ):
        raise ValueError("旬首规则参考须保留完整六例，不得删例或重复")
    deferred = manifest["deferred_source_readings"]
    if not any(
        d["section"] == "卷二·伏干格" and d["day"] == "甲申" and d["hour"] == "壬申"
        for d in deferred
    ):
        raise ValueError("须保留尚未核明的日甲例，不能将未实现项删去判通过")
    if len(manifest["pair_definitions"]) != 2 or {
        (d["heaven_stem"], d["earth_stem"], d["name"])
        for d in manifest["pair_definitions"]
    } != {("庚", "癸", "大格"), ("庚", "壬", "小格")}:
        raise ValueError("须保留大格、小格两条原文定义")
    disagreements: list[dict[str, Any]] = []
    matched = 0
    for case in cases:
        ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        leader = _qimen_zhifu_zhishi(case["hour"], ju, dun_type=case["dun"])
        palaces = _qimen_build_palaces(
            time_ganzhi=case["hour"],
            ju_text=ju,
            dun_type=case["dun"],
            current_term="冬至",
        )
        moment = datetime(2026, 1, 1, 12)
        seed = MetaphysicsSeed(
            moment,
            moment,
            "Asia/Shanghai",
            None,
            False,
            0.0,
            {"month": ("丙", "寅")},
            {"current_solar_term": {"name": "冬至"}},
        )
        board = enrich_qimen_evidence(
            {
                "ju_text": ju,
                "palaces": palaces,
                "ju_method": "zhirun",
                "ju_term": "冬至",
                "day_ganzhi": "甲子",
                "time_ganzhi": case["hour"],
                "kongwang": "戌亥空",
            },
            seed=seed,
            leader=leader,
        )
        palace = next(p for p in palaces if p["trigram"] == case["palace"])
        differences = []
        for field, expected in case["observations"].items():
            if palace[field] != expected:
                differences.append(
                    {"field": field, "expected": expected, "actual": palace[field]}
                )
        for expected_key, actual_key in [
            ("leader_star", "star"),
            ("leader_at", "star_gong"),
            ("leader_source", "source_gong"),
        ]:
            if expected_key in case and case[expected_key] != leader[actual_key]:
                differences.append(
                    {
                        "field": expected_key,
                        "expected": case[expected_key],
                        "actual": leader[actual_key],
                    }
                )
        if not any(
            p["rule_id"] == case["rule_id"]
            and p["name"] == case["name"]
            and p["palace"] == palace["name"]
            for p in board["patterns"]
        ):
            differences.append(
                {
                    "field": "pattern",
                    "expected": case["name"],
                    "actual": "not_matched_in_source_palace",
                }
            )
        matched += not differences
        disagreements.extend({"case_id": case["id"], **d} for d in differences)
    for definition in manifest["pair_definitions"]:
        pair = definition["heaven_stem"], definition["earth_stem"]
        actual = STEM_PATTERNS.get(pair, ("not_implemented", ""))[0]
        if actual != definition["name"]:
            disagreements.append(
                {
                    "case_id": "pair:" + "".join(pair),
                    "field": "name",
                    "expected": definition["name"],
                    "actual": actual,
                }
            )
    return {
        "method_id": "qimen_current_hour_head_source_examples_v5",
        "source": manifest["source_url"],
        "case_count": 6,
        "matched_case_count": matched,
        "literal_pair_definitions_checked": 2,
        "disagreements": disagreements,
        "deferred_unpassed_count": len(deferred),
        "deferred_source_readings": deferred,
        "status": (
            "selected_examples_match_with_deferred_scope"
            if not disagreements
            else "disagreements"
        ),
        "non_jiazi_source_examples_independently_verified": False,
        "reference_input_scope": "printed ju and hour; no historical civil date reconstruction or real-world outcome prediction",
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }


def audit_chapter_profiles(directory: Path) -> dict[str, Any]:
    """Check frozen chapter readings, keeping their incompatible definitions."""
    manifest = json.loads((directory / "sources-and-profiles.json").read_text())
    for file_key, digest_key in [
        ("excerpt_file", "excerpt_sha256"),
        ("diagram_excerpt_file", "diagram_excerpt_sha256"),
    ]:
        source = (directory / manifest[file_key]).resolve()
        if not source.is_relative_to(directory.resolve().parent):
            raise ValueError("奇门章节影印路径越出参考目录")
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest[digest_key]:
            raise ValueError("奇门章节影印参考文件指纹不一致")
    diagrams = manifest["god_diagrams"]
    required = {
        (d, j, "甲子") for d, j in [("阳遁", 1), ("阳遁", 5), ("阴遁", 9), ("阴遁", 5)]
    }
    if (
        len(diagrams) != 4
        or {(c["dun"], c["ju"], c["hour"]) for c in diagrams} != required
    ):
        raise ValueError("奇门章节参考须保留四幅阴阳与寄宫圆图")
    profiles = manifest["season_profiles"]
    if len(profiles) != 3 or {p["profile"] for p in profiles} != {
        "yanyi_vol1_verse",
        "yanyi_vol3_table",
        "yanyi_vol3_prose",
    }:
        raise ValueError("奇门章节参考须保留三种旺衰异文")
    disagreements: list[dict[str, Any]] = []

    def compare(case: str, expected: Any, actual: Any) -> None:
        if expected != actual:
            disagreements.append({"case": case, "expected": expected, "actual": actual})

    compare(
        "god_text_sequence",
        manifest["god_text"]["sequence"],
        GOD_PROFILES["yanyi_text"]["sequence"],
    )
    for case in diagrams:
        if set(case["gods"]) != set("坎艮震巽离坤兑乾"):
            raise ValueError("奇门四幅圆图须各保留完整八宫")
        ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        palaces = _qimen_build_palaces(
            time_ganzhi=case["hour"],
            ju_text=ju,
            dun_type=case["dun"],
            current_term="冬至",
            god_profile="yanyi_diagrams",
        )
        compare(
            case["id"],
            case["gods"],
            {p["trigram"]: p["god"] for p in palaces if p["trigram"] != "中"},
        )
    table_cases = 0
    relation_cases = 0
    branch_elements = dict(zip("子丑寅卯辰巳午未申酉戌亥", "水土木木土火火土金金土水"))
    for profile in profiles:
        name = profile["profile"]
        if name == "yanyi_vol3_table":
            rows = profile["states_by_star_element"]
            if set(rows) != set("木火土金水"):
                raise ValueError("奇门旺相表须保留五行各十二月")
            for element, states in rows.items():
                branches = "".join(states.values())
                if len(branches) != 12 or set(branches) != set(branch_elements):
                    raise ValueError("奇门旺相表须保留五行各十二月，不得漏月或重复")
                for state, months in states.items():
                    for month in months:
                        table_cases += 1
                        compare(
                            f"{name}:{element}:{month}",
                            state,
                            star_season_state(element, branch_elements[month], name),
                        )
        else:
            relations = profile["states_by_relation"]
            pairs = {
                "same_element": ("水", "水"),
                "star_generates_month": ("水", "木"),
                "month_generates_star": ("水", "金"),
                "star_controls_month": ("水", "火"),
                "month_controls_star": ("水", "土"),
            }
            if set(relations) != set(pairs):
                raise ValueError("奇门旺衰正文须保留五种生克关系")
            for relation, (star, month_element) in pairs.items():
                relation_cases += 1
                compare(
                    f"{name}:{relation}",
                    relations[relation],
                    star_season_state(star, month_element, name),
                )
    return {
        "method_id": "qimen_siku_chapter_variants_v4",
        "status": (
            "selected_source_observations_match"
            if not disagreements
            else "disagreements"
        ),
        "god_text_sequence_checked": True,
        "god_diagram_cases": len(diagrams),
        "god_palace_observations": len(diagrams) * 8,
        "season_table_month_cases": table_cases,
        "season_verse_prose_relation_cases": relation_cases,
        "disagreements": disagreements,
        "source_variants_retained": [
            "正文白虎玄武／圆图勾陈朱雀",
            "卷一赋／卷三表／卷三正文旺衰差异",
        ],
        "previous_unresolved_cases_erased": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }


def audit_numeric_tables(directory: Path) -> dict[str, Any]:
    """Compare all 1080 printed leader rows, retaining raw palace 5 before hosting.

    The table precedes its matching diagram. Coverage is fixed here so a
    truncated manifest cannot turn missing difficult rows into passing cases.
    """
    manifest = json.loads((directory / "sources-and-tables.json").read_text())
    excerpt = (directory / manifest["excerpt_file"]).resolve()
    if not excerpt.is_relative_to(directory.resolve()):
        raise ValueError("奇门数表影印路径越出参考目录")
    if hashlib.sha256(excerpt.read_bytes()).hexdigest() != manifest["excerpt_sha256"]:
        raise ValueError("奇门数表影印参考文件指纹不一致")
    cross_check = manifest.get("digital_cross_check")
    if cross_check:
        linked_files = [
            (
                cross_check["commons_metadata_file"],
                cross_check["commons_metadata_sha256"],
            ),
            *[
                (c["rendered_image_file"], c["rendered_image_sha256"])
                for c in cross_check["cases"]
            ],
        ]
        for filename, expected_digest in linked_files:
            linked = (directory / filename).resolve()
            if not linked.is_relative_to(directory.resolve()):
                raise ValueError("奇门数表交叉影印路径越出参考目录")
            if hashlib.sha256(linked.read_bytes()).hexdigest() != expected_digest:
                raise ValueError("奇门数表交叉影印参考文件指纹不一致")
    tables = manifest["tables"]
    required = {(d, n) for d in ["阳遁", "阴遁"] for n in range(1, 10)}
    if len(tables) != 18 or {(t["dun"], t["ju"]) for t in tables} != required:
        raise ValueError("奇门原典数表必须保留完整十八局，不得删局或重复")
    numerals = {gua: str(i + 1) for i, gua in enumerate("坎坤震巽中乾兑艮离")}
    summaries: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    for table in tables:
        if (
            table["column_order"] != ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"]
            or len(table["leader_star_codes"]) != 6
            or len(table["leader_door_codes"]) != 6
            or len(table["palace_pairs"]) != 6
        ):
            raise ValueError("奇门原典数表须逐局保留六旬与星门表头")
        ju = f'{table["dun"]}{"一二三四五六七八九"[table["ju"] - 1]}局上元'
        matched = 0
        for column, text in enumerate(table["palace_pairs"]):
            pairs = text.split()
            if len(pairs) != 10 or any(
                len(pair) != 2 or any(c not in "123456789" for c in pair)
                for pair in pairs
            ):
                raise ValueError("奇门原典数表每旬须保留十时、每时两个原始宫数")
            for row, pair in enumerate(pairs):
                index = column * 10 + row
                hour = (
                    "甲乙丙丁戊己庚辛壬癸"[index % 10]
                    + "子丑寅卯辰巳午未申酉戌亥"[index % 12]
                )
                leader = _qimen_zhifu_zhishi(hour, ju, dun_type=table["dun"])
                expected = {
                    "raw_star_gong": pair[0],
                    "raw_door_gong": pair[1],
                    "star": table["leader_star_codes"][column],
                    "door": table["leader_door_codes"][column],
                }
                actual = {
                    "raw_star_gong": numerals[leader["raw_star_gong"]],
                    "raw_door_gong": numerals[leader["raw_door_gong"]],
                    "star": leader["star"],
                    "door": leader["door"],
                }
                differences = [
                    {"field": key, "expected": value, "actual": actual[key]}
                    for key, value in expected.items()
                    if value != actual[key]
                ]
                matched += int(not differences)
                disagreements.extend(
                    {
                        "dun": table["dun"],
                        "ju": table["ju"],
                        "hour": hour,
                        "table_scan_page": table["table_scan_page"],
                        "table_half": table["table_half"],
                        "column_xun": table["column_order"][column],
                        **item,
                    }
                    for item in differences
                )
        summaries.append(
            {
                "dun": table["dun"],
                "ju": table["ju"],
                "table_scan_page": table["table_scan_page"],
                "table_half": table["table_half"],
                "case_count": 60,
                "matched_case_count": matched,
            }
        )
    return {
        "method_id": "qimen_all_eighteen_printed_numeric_tables_v3",
        "source": manifest["source_url"],
        "excerpt_sha256": manifest["excerpt_sha256"],
        "table_count": 18,
        "case_count": 1080,
        "numeric_palace_observation_count": 2160,
        "leader_heading_pairs": 108,
        "matched_case_count": sum(s["matched_case_count"] for s in summaries),
        "tables": summaries,
        "disagreements": disagreements,
        "status": (
            "incomplete_with_disagreements"
            if disagreements
            else "printed_observations_match"
        ),
        "whole_board_conformance_established": False,
        "whole_book_conformance_established": False,
        "scope": "核对原始值符、值使宫位及表头星门；不把这些字段符合扩为天盘全层、全书或现实预测符合。",
        "real_world_efficacy": "not_tested",
        "cross_digital_file_collation": cross_check,
    }


def audit_scan_examples(directory: Path) -> dict[str, Any]:
    manifest = json.loads(
        (directory / "sources-and-cases.json").read_text(encoding="utf-8")
    )
    scan = manifest["scan"]
    excerpt = (directory / scan["excerpt_file"]).resolve()
    if not excerpt.is_relative_to(directory.resolve()):
        raise ValueError("奇门影印路径越出参考目录")
    if hashlib.sha256(excerpt.read_bytes()).hexdigest() != scan["excerpt_sha256"]:
        raise ValueError("奇门影印参考文件指纹不一致")
    rows = []
    for case in manifest["cases"]:
        ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        leader = _qimen_zhifu_zhishi(case["hour"], ju, dun_type=case["dun"])
        palaces = {
            p["trigram"]: p
            for p in _qimen_build_palaces(
                time_ganzhi=case["hour"],
                ju_text=ju,
                dun_type=case["dun"],
                current_term="冬至",
            )
        }
        discrepancies = []
        for observation in case["observations"]:
            actual = palaces[observation["trigram"]][observation["field"]]
            expected = observation.get("equals", observation.get("contains"))
            ok = actual == expected if "equals" in observation else expected in actual
            if not ok:
                discrepancies.append(
                    {
                        "trigram": observation["trigram"],
                        "field": observation["field"],
                        "expected": expected,
                        "actual": actual,
                        "mode": "equals" if "equals" in observation else "contains",
                    }
                )
        rows.append(
            {
                "id": case["id"],
                "scan_pages": case["scan_pages"],
                "status": "disagreement" if discrepancies else "observations_match",
                "discrepancies": discrepancies,
                "leader": leader,
            }
        )
    disagreements = [
        {"case_id": r["id"], **d} for r in rows for d in r["discrepancies"]
    ]
    return {
        "method_id": "qimen_selected_scan_examples_v2",
        "source": scan["url"],
        "excerpt_sha256": scan["excerpt_sha256"],
        "case_count": len(rows),
        "matched_case_count": sum(not r["discrepancies"] for r in rows),
        "rows": rows,
        "disagreements": disagreements,
        "status": "incomplete" if disagreements else "selected_observations_match",
        "whole_book_conformance_established": False,
        "bibliographic_authentication": scan["kind"],
        "real_world_efficacy": "not_tested",
    }


def verify_qimen_pattern_quotes(
    payload: dict[str, Any], claims: list["CalculationClaim"]
) -> dict[str, Any]:
    """Verify whole same-run pattern quotations, including adverse qualifications.

    This rejects cherry-picked subfields as a pattern quotation. It does not
    grade surrounding natural language or authenticate a self-created receipt.
    """
    import re

    from fatebridge.validation.claims import verify_calculation_claims

    report = verify_calculation_claims(payload, claims)
    errors = list(report["errors"])
    for index, claim in enumerate(claims):
        if not re.fullmatch(r"qimen\.patterns\.(0|[1-9][0-9]*)", claim.path):
            errors.append(
                {"claim_index": index, "code": "whole_qimen_pattern_required"}
            )
    return {
        "method_id": "same_run_whole_qimen_pattern_quotes_v1",
        "status": (
            "rejected" if errors or not claims else "verified_structured_pattern_quotes"
        ),
        "checked_claim_count": len(claims),
        "errors": errors,
        "free_text_semantics_validated": False,
        "real_world_efficacy_validated": False,
        "scope": "只核同run完整盘局的整条格局引用，包括附加条件、冲突与来源；不证明自由文本解释、原典一致性或现实预测效力。原始回执必须另从可信执行端核对。",
    }
