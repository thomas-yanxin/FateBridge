"""External transcription fixtures and exhaustive structural regression checks.

The full combinatorial checks are correctness properties, never independent
evidence that any real-world event can be predicted.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.almanac import build_calendar_context, get_solar_terms_for_year
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.divination import derive_meihua_hexagram, lookup_hexagram_by_code
from fatebridge.core.liuyao_evidence import ADVANCES, branch_facts, xunkong
from fatebridge.core.local_techniques.sixyao import (
    _LIUCHONG_HEXAGRAM_CODES,
    _LIUHE_HEXAGRAM_CODES,
    _build_sixyao_enrichment,
    _coin_lines_and_meta,
    _derive_changed_code,
    _derive_gua_code,
    build_sixyao_result,
)
from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.core.zhouyi import classical_hexagram
from scripts.build_zhouyi_corpus import build

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = json.loads((FIXTURES / "zhouyi-wikisource.json").read_text())
CORPUS = build(SOURCE)
ZENGSHAN = json.loads((FIXTURES / "liuyao-zengshan-sources.json").read_text())
CODES = ["".join(bits) for bits in product("01", repeat=6)]
INPUT = {"date": "2026-10-22", "time": "12:00:00", "zone": "Asia/Shanghai"}


def test_frozen_sources_and_packaged_corpus_are_reproducible():
    for record in [
        SOURCE["index"],
        *SOURCE["chapters"],
        ZENGSHAN["main"],
        *ZENGSHAN["chapters"],
    ]:
        assert (
            hashlib.sha256(record["wikitext"].encode()).hexdigest()
            == record["wikitext_sha256"]
        )
        assert "oldid=" + str(record["revision"]) in record["source_url"]
    actual = json.loads(
        (
            Path(__file__).parents[1] / "src/fatebridge/data/classical/zhouyi.json"
        ).read_text()
    )
    assert actual == CORPUS
    assert len(CORPUS["chapters"]) == 64
    assert sum(len(c["yaoci"]) for c in CORPUS["chapters"]) == 384
    assert sum(c["special"] is not None for c in CORPUS["chapters"]) == 2


def test_all_palaces_and_shiying_match_independent_published_table():
    table = SOURCE["index"]["wikitext"].split("== 分宮卦象次序表 ==")[1]
    table = re.sub(r"-\{([^{}]+)\}-", r"\1", table)
    rows = [
        row for row in re.findall(r"\n!([^\n]+)\n\|([^\n]+)", table) if "為" in row[0]
    ]
    assert len(rows) == 8
    traditional = str.maketrans({"兌": "兑", "離": "离", "恆": "恒", "遯": "遁"})
    reference = {
        c["name"].translate(traditional): c["code"] for c in CORPUS["chapters"]
    }
    checked = set()
    for heading, rest in rows:
        palace = heading[0].translate(traditional)
        for index, full_name in enumerate([heading, *rest.strip().split("||")]):
            full_name = full_name.strip().translate(traditional)
            short = (
                palace
                if index == 0
                else max(
                    (name for name in reference if full_name.endswith(name)), key=len
                )
            )
            code = reference[short]
            info, _ = _build_sixyao_enrichment(code, code, "甲")
            assert info["current_palace"] == palace
            assert info["shi_line"] == [6, 1, 2, 3, 4, 5, 4, 3][index]
            assert abs(info["shi_line"] - info["ying_line"]) == 3
            checked.add(code)
    assert checked == set(CODES)


def test_nazhi_of_all_64_hexagrams_matches_frozen_chapter_four():
    raw = next(p["wikitext"] for p in ZENGSHAN["chapters"] if p["title"].endswith("/4"))
    rows = re.findall(r"\* (.)在內：([^。]+)。.在外[：；]([^。]+)。", raw)
    assert len(rows) == 8
    # Explicit correction, not a silent change to the frozen transcription:
    # 辰在內 is a transcription typo for 艮在內, as the chapter's 8-trigram
    # enumeration and the palace diagram establish. See audit document.
    translate = str.maketrans({"辰": "艮", "離": "离", "兌": "兑"})
    tables = {
        name.translate(translate): (
            re.findall(r"[子丑寅卯辰巳午未申酉戌亥]", lower),
            re.findall(r"[子丑寅卯辰巳午未申酉戌亥]", upper),
        )
        for name, lower, upper in rows
    }
    for code in CODES:
        gua = lookup_hexagram_by_code(code)
        _, lines = _build_sixyao_enrichment(code, code, "甲")
        assert [row["branch"] for row in lines] == tables[gua["lower"]["name"]][
            0
        ] + tables[gua["upper"]["name"]][1]


def test_all_ten_six_clash_and_eight_six_combination_hexagrams():
    clashes, combinations = set(), set()
    partner = dict(zip("子丑寅亥卯戌辰酉巳申午未", "丑子亥寅戌卯酉辰申巳未午"))
    branches = "子丑寅卯辰巳午未申酉戌亥"
    for code in CODES:
        _, lines = _build_sixyao_enrichment(code, code, "甲")
        pairs = [(lines[i]["branch"], lines[i + 3]["branch"]) for i in range(3)]
        if all((branches.index(a) - branches.index(b)) % 12 == 6 for a, b in pairs):
            clashes.add(code)
        if all(partner[a] == b for a, b in pairs):
            combinations.add(code)
    assert clashes == _LIUCHONG_HEXAGRAM_CODES
    assert combinations == _LIUHE_HEXAGRAM_CODES
    assert len(clashes) == 10 and len(combinations) == 8


def test_need_to_song_matches_zengshan_chapter_seven_without_static_transformations():
    result = build_sixyao_result(**INPUT, gua_code="111010", changed_code="010111")
    assert result["hexagram_info"]["current_palace"] == "坤"
    assert result["moving_lines"] == [1, 3, 4, 6]
    assert [line.get("changed_branch") for line in result["lines"]] == [
        "寅",
        None,
        "午",
        "午",
        None,
        "戌",
    ]
    assert [line.get("changed_liuqin") for line in result["lines"]] == [
        "官鬼",
        None,
        "父母",
        "父母",
        None,
        "兄弟",
    ]


def test_every_rule_trace_points_to_actual_returned_facts():
    result = build_sixyao_result(**INPUT, gua_code="111010", changed_code="010111")
    trace = result["liuyao_evidence"]["rule_trace"]
    assert {row["rule_id"] for row in trace} == {
        "palace_shiying_nazhi_kinship_six_gods",
        "day_month_branch_relations",
        "moving_line_back_relation_advance_retreat",
        "missing_kinship_hidden_candidates",
        "actual_moving_classical_text",
        "seasonal_activity_conditions",
        "parent_only_transformation",
        "explicit_focus_roles",
        "day_condition_windows",
        "three_harmony_conditions",
        "hidden_support_conditions",
        "role_condition_effects",
        "grounded_strength_and_tombs",
        "separate_body_region_and_active_line_fanfu",
        "void_conditions_and_outgoing_obstructions",
        "progression_four_clauses_and_explicit_horizon",
        "activity_control_targets_and_injured_static_control",
        "day_clash_break_fill_and_moving_scatter",
        "outgoing_generation_and_target_reception",
        "back_generation_support_for_original_actions",
        "successive_generation_path_conditions",
        "partial_stage_query_knowledge",
        "earth_cessation_independent_support_exception",
        "metal_si_day_growth_month_support",
        "metal_si_day_growth_moving_support",
        "si_yin_shen_scoped_growth_exclusion",
        "day_value_month_only_opposition_exception",
        "current_void_fill_directed_control",
    }
    for row in trace:
        actual = result
        for part in row["fact_path"].split("."):
            actual = actual[int(part)] if isinstance(actual, list) else actual[part]
        assert actual is not None
        if row["rule_id"] == "metal_si_day_growth_moving_support":
            scan = result["liuyao_evidence"]["conditional_analysis"]["classical_scan"]
            assert row["source_sha256"] == scan["source"]["sha256"]
            assert row["proof_paths"]
            expected_sources = set()
            for path in row["proof_paths"]:
                proof = result
                for part in path.split("."):
                    proof = proof[int(part)] if isinstance(proof, list) else proof[part]
                assert proof["source_path"] == path
                assert proof["source_sha256"] == row["source_sha256"]
                assert proof["ruleset_id"] == "zengshan_metal_si_moving_support_v34"
                assert proof["ruleset_version"] == "34.0.0"
                expected_sources.add(proof["source_url"])
                if "application_source_url" in proof:
                    assert proof["application_source_sha256"] == row["source_sha256"]
                    assert (
                        proof["application_source_url"]
                        == scan["source"]["url"] + "#page=110"
                    )
                    assert "跨章适用" in proof["application_interpretation"]
                    expected_sources.add(proof["application_source_url"])
            assert row["sources"] == sorted(expected_sources)
        for source in row["sources"]:
            if "oldid=" in source:
                continue
            scan = result["liuyao_evidence"]["conditional_analysis"]["classical_scan"]
            document, page = source.rsplit("#page=", 1)
            assert document == scan["source"]["url"]
            collated_pages = {p for c in scan["collations"] for p in c["pdf_pages"]}
            if row["rule_id"] == "metal_si_day_growth_moving_support":
                from scripts.build_liuyao_metal_moving_profile import (
                    build as moving_profile,
                )

                profile = moving_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
                hidden = json.loads(
                    (FIXTURES / "liuyao_hidden_v14/profile.json").read_text()
                )
                assert hidden["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in hidden["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "current_void_fill_directed_control":
                from scripts.build_liuyao_void_control_profile import (
                    build as void_control_profile,
                )

                profile = void_control_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(c["pdf_page"] for c in profile["clauses"])
            if row["rule_id"] == "role_condition_effects":
                role_source = json.loads(
                    (FIXTURES / "liuyao_effects_v4/profile.json").read_text()
                )["source"]
                assert role_source["sha256"] == scan["source"]["sha256"]
                collated_pages.update(role_source["pages"])
            if row["rule_id"] == "separate_body_region_and_active_line_fanfu":
                from scripts.build_liuyao_fanfu_profile import build as fanfu_profile

                profile = fanfu_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "void_conditions_and_outgoing_obstructions":
                from scripts.build_liuyao_void_profile import build as void_profile

                profile = void_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "activity_control_targets_and_injured_static_control":
                from scripts.build_liuyao_control_profile import (
                    build as control_profile,
                )

                profile = control_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(c["pdf_page"] for c in profile["clauses"])
            if row["rule_id"] == "day_clash_break_fill_and_moving_scatter":
                from scripts.build_liuyao_clash_profile import build as clash_profile

                profile = clash_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "outgoing_generation_and_target_reception":
                from scripts.build_liuyao_generation_profile import (
                    build as generation_profile,
                )

                profile = generation_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "back_generation_support_for_original_actions":
                from scripts.build_liuyao_rescue_profile import build as rescue_profile

                profile = rescue_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "successive_generation_path_conditions":
                from scripts.build_liuyao_routing_profile import (
                    build as routing_profile,
                )

                profile = routing_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "partial_stage_query_knowledge":
                from scripts.build_liuyao_stage_profile import build as stage_profile

                profile = stage_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "earth_cessation_independent_support_exception":
                from scripts.build_liuyao_cessation_profile import (
                    build as cessation_profile,
                )

                profile = cessation_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "metal_si_day_growth_month_support":
                from scripts.build_liuyao_growth_profile import build as growth_profile

                profile = growth_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "si_yin_shen_scoped_growth_exclusion":
                from scripts.build_liuyao_penalty_profile import (
                    build as penalty_profile,
                )

                profile = penalty_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            if row["rule_id"] == "day_value_month_only_opposition_exception":
                from scripts.build_liuyao_month_break_profile import (
                    build as month_break_profile,
                )

                profile = month_break_profile()
                assert profile["source"]["sha256"] == scan["source"]["sha256"]
                collated_pages.update(
                    p for c in profile["clauses"] for p in c["pdf_pages"]
                )
            assert int(page) in collated_pages
            raw = FIXTURES / "liuyao_scan_v3" / scan["source"]["file"]
            assert (
                hashlib.sha256(raw.read_bytes()).hexdigest() == scan["source"]["sha256"]
            )


def test_every_coin_configuration_has_exact_base_changed_and_moving_lines():
    for tosses in product((6, 7, 8, 9), repeat=6):
        lines, _ = _coin_lines_and_meta(list(tosses))
        assert _derive_gua_code(lines) == "".join(str(n % 2) for n in tosses)
        assert _derive_changed_code(lines) == "".join(
            "1" if n in (6, 7) else "0" for n in tosses
        )
        assert [line["change"] for line in lines] == [n in (6, 9) for n in tosses]


def test_all_4096_base_changed_pairs_keep_static_lines_untransformed():
    for current in CODES:
        for changed in CODES:
            result = build_sixyao_result(
                **INPUT, gua_code=current, changed_code=changed
            )
            expected = [i + 1 for i in range(6) if current[i] != changed[i]]
            assert result["moving_lines"] == expected
            fanfu = result["liuyao_evidence"]["fanfu"]
            assert [r["position"] for r in fanfu["moving_line_relations"]] == expected
            for region in fanfu["regions"]:
                assert not set(region["static_comparison_positions"]) & set(expected)
                if not region["trigram_changed"]:
                    assert region["nazhi_relation"] == "未动"
            for transformed in fanfu["moving_line_relations"]:
                p = transformed["position"]
                assert (
                    transformed["changed_branch"]
                    == result["lines"][p - 1]["changed_branch"]
                )
            if not expected:
                assert not result["pattern_flags"]["liuchong_changed"]
                assert not result["pattern_flags"]["liuhe_changed"]
            assert [
                v["position"] for v in result["classical_text_evidence"]["moving_yaoci"]
            ] == expected
            for line in result["lines"]:
                assert ("changed_branch" in line) is line["change"]
                assert ("changed_liuqin" in line) is line["change"]
            for edge in result["liuyao_evidence"]["conditional_analysis"][
                "interaction_edges"
            ]:
                assert edge["target_kind"] == "base"
                if edge["source_kind"] == "changed":
                    assert edge["source_position"] in expected
                    assert edge["source_position"] == edge["target_position"]
            conditional = result["liuyao_evidence"]["conditional_analysis"]
            for candidate in conditional["three_harmony"]["candidates"]:
                members = candidate["members"]
                branches = {m["branch"] for m in members}
                assert branches <= set(candidate["group_branches"])
                assert len(branches) == len(members)
                for member in members:
                    row = result["lines"][member["position"] - 1]
                    if member["location"] == "changed":
                        assert member["position"] in expected
                        assert member["branch"] == row["changed_branch"]
                    else:
                        assert member["branch"] == row["branch"]
                if candidate["pattern"] in ("inner_changed", "outer_changed"):
                    endpoints = (
                        {1, 3} if candidate["pattern"] == "inner_changed" else {4, 6}
                    )
                    assert {m["position"] for m in members} == endpoints
                    assert endpoints <= set(expected)
                if candidate["status"] == "formation_conditions_matched":
                    assert len(branches) == 3
                    assert len(candidate["active_positions"]) >= 2
                    assert candidate["obstructions"] == []
            present_kinships = {r["liuqin"] for r in result["lines"]} | {
                r["changed_liuqin"] for r in result["lines"] if r["change"]
            }
            assert all(
                h["liuqin"] not in present_kinships
                for h in result["liuyao_evidence"]["hidden_spirits"]
            )


def test_six_gods_for_all_ten_stems_match_independent_source_table():
    raw = next(
        p["wikitext"] for p in ZENGSHAN["chapters"] if p["title"].endswith("/18")
    )
    table = raw.split("|}")[0]
    rows = re.findall(r"^\| '''[^']+''' \|\| (.+)$", table, re.M)
    assert len(rows) == 6
    names = str.maketrans({"元": "玄", "靑": "青", "龍": "龙", "陳": "陈", "滕": "腾"})
    groups = [
        [x.strip().translate(names) for x in row.split("||")] for row in reversed(rows)
    ]
    for stem, column in zip("甲乙丙丁戊己庚辛壬癸", [0, 0, 1, 1, 2, 3, 4, 4, 5, 5]):
        _, lines = _build_sixyao_enrichment("111111", "111111", stem)
        assert [line["liushen"] for line in lines] == [row[column] for row in groups]


@pytest.mark.parametrize(
    "day_ganzhi,expected",
    [
        ("甲子", "戌亥"),
        ("甲戌", "申酉"),
        ("甲申", "午未"),
        ("甲午", "辰巳"),
        ("甲辰", "寅卯"),
        ("甲寅", "子丑"),
    ],
)
def test_xunkong_matches_all_sixty_sexagenary_days(day_ganzhi, expected):
    stems, branches = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
    start = branches.index(day_ganzhi[1])
    for day in range(10):
        assert xunkong(stems[day] + branches[(start + day) % 12]) == list(expected)


def test_flags_do_not_infer_xunkong_means_ineffective_or_day_clash_means_hidden_movement():
    facts = branch_facts("子", "子", "午", ["子", "丑"])
    assert facts["is_month_branch"] and facts["is_day_clash"] and facts["is_xunkong"]
    assert "is_andong" not in facts and "is_ineffective" not in facts
    assert set(ADVANCES.items()) == {
        ("亥", "子"),
        ("寅", "卯"),
        ("巳", "午"),
        ("申", "酉"),
        ("丑", "辰"),
        ("辰", "未"),
        ("未", "戌"),
    }
    assert "戌" not in ADVANCES


def test_fugua_candidates_only_fill_missing_categories_and_keep_flying_relations():
    result = build_sixyao_result(**INPUT, gua_code="100000")  # 坤宫地雷复
    hidden = result["liuyao_evidence"]["hidden_spirits"]
    # 寅木官鬼 already appears at 初爻, so only 父母 is missing.
    assert [
        (x["position"], x["liuqin"], x["branch"], x["flying_branch"]) for x in hidden
    ] == [(2, "父母", "巳", "寅")]
    assert all(
        x["liuqin"] not in {line["liuqin"] for line in result["lines"]} for x in hidden
    )


def test_original_verses_are_distinct_from_modern_summaries_and_copy_safe():
    result = build_sixyao_result(**INPUT, gua_code="111111", changed_code="000000")
    assert result["descriptions"]["111111"]["卦辞"] == "乾：元亨。利貞。"
    assert result["descriptions"]["111111"]["象曰"] == "天行健，君子以自強不息。"
    assert (
        result["current_hexagram"]["meaning_source_kind"] == "modern_editorial_summary"
    )
    texts = result["classical_text_evidence"]
    assert len(texts["moving_yaoci"]) == 6
    assert texts["all_moving_special"] == {"label": "用九", "text": "見羣龍无首，吉。"}
    result["current_hexagram"]["classical"]["yaoci"][0]["text"] = "altered"
    assert classical_hexagram("111111")["yaoci"][0]["text"] == "潛龍勿用。"
    assert (
        result["liuyao_evidence"]["prediction_validation"]["status"]
        == "not_established"
    )
    result["liuyao_evidence"]["source_revisions"]["4"]["revision"] = -1
    fresh = build_sixyao_result(**INPUT, gua_code="111111")
    assert fresh["liuyao_evidence"]["source_revisions"]["4"]["revision"] == 2100293


@pytest.mark.parametrize(
    "bad",
    [
        {"lines": [{"value": 0}] * 5},
        {"lines": [{"value": 0}] * 7},
        {"lines": [{"value": "0"}] * 6},
        {"lines": [{"value": False}] * 6},
        {"lines": [{"value": 0, "change": "false"}] * 6},
        {"coins": [7.9] * 6},
        {"coins": [True] * 6},
        {"gua_code": "111x111"},
        {"gua_code": ""},
        {"changed_code": "111111"},
        {"gua_code": "111111", "lines": [{"value": 0}] * 6},
        {"coins": [7] * 6, "gua_code": "000000"},
    ],
)
def test_invalid_or_conflicting_inputs_never_silently_change_the_cast(bad):
    with pytest.raises(ValueError):
        build_sixyao_result(**INPUT, **bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"coins": [7.0] * 6},
        {"coins": [False] * 6},
        {"lines": [{"value": "0"}] * 6},
        {"lines": [{"value": 0}] * 4},
        {"gua_code": "111x111"},
    ],
)
def test_request_schema_preserves_strict_values(bad):
    with pytest.raises(ValidationError):
        SixYaoRequest.model_validate({**INPUT, **bad})


def test_lunar_year_is_used_between_lichun_and_lunar_new_year():
    # HKO: lunar new year is 2026-02-17; 立春 precedes it on 02-04.
    moment = datetime(2026, 2, 10, 12)
    pillars = BaZiCalendar.get_four_pillars(moment, timezone_name="Asia/Shanghai")
    context = build_calendar_context(moment, pillars=pillars)
    assert pillars["year"][1] == "午"
    lunar = context["lunar_calendar"]
    assert lunar["year"] == 2025
    assert lunar["meihua"]["seed"]["year_branch"] == "巳"
    expected = derive_meihua_hexagram(
        year_branch="巳", lunar_month=12, lunar_day=23, hour_branch="午"
    )
    assert lunar["meihua"] == expected


def test_midnight_lunar_date_and_23_hour_ganzhi_are_separate_explicit_clocks():
    before = build_sixyao_result(date="2026-02-16", time="22:59:59", gua_code="111111")
    late = build_sixyao_result(date="2026-02-16", time="23:00:00", gua_code="111111")
    assert before["nongli"]["dayGanZi"] != late["nongli"]["dayGanZi"]
    assert before["nongli"]["dayInt"] == late["nongli"]["dayInt"]
    assert "23:00" in late["liuyao_evidence"]["calendar_conventions"]["day_boundary"]


def test_every_2026_lunar_date_matches_hko_published_table():
    metadata = json.loads((FIXTURES / "liuyao-hko-2026.metadata.json").read_text())
    assert (
        hashlib.sha256((FIXTURES / "liuyao-hko-2026.txt").read_bytes()).hexdigest()
        == metadata["source_sha256"]
    )
    raw = (FIXTURES / "liuyao-hko-2026.txt").read_text(encoding="utf-8-sig")
    rows = re.findall(r"2026年(\d+)月(\d+)日\s+(\S+)\s+星期", raw)
    assert len(rows) == 365
    chinese_days = [
        "初一",
        "初二",
        "初三",
        "初四",
        "初五",
        "初六",
        "初七",
        "初八",
        "初九",
        "初十",
        "十一",
        "十二",
        "十三",
        "十四",
        "十五",
        "十六",
        "十七",
        "十八",
        "十九",
        "二十",
        "廿一",
        "廿二",
        "廿三",
        "廿四",
        "廿五",
        "廿六",
        "廿七",
        "廿八",
        "廿九",
        "三十",
    ]
    month = 11  # 2026-01-01 falls in 乙巳年十一月; HKO 2025 table.
    for m, d, label in rows:
        lunar = build_calendar_context(datetime(2026, int(m), int(d), 12))[
            "lunar_calendar"
        ]
        if label.endswith("月"):
            month = {
                "十二月": 12,
                "正月": 1,
                "二月": 2,
                "三月": 3,
                "四月": 4,
                "五月": 5,
                "六月": 6,
                "七月": 7,
                "八月": 8,
                "九月": 9,
                "十月": 10,
                "十一月": 11,
            }[label]
            day = 1
        else:
            day = chinese_days.index(label) + 1
        assert (lunar["month"], lunar["day"], lunar["is_leap_month"]) == (
            month,
            day,
            False,
        )


def test_all_24_solar_term_dates_match_hko_and_twelve_jie_switch_month_at_instant():
    raw = (FIXTURES / "liuyao-hko-2026.txt").read_text(encoding="utf-8-sig")
    rows = re.findall(r"2026年(\d+)月(\d+)日\s+\S+\s+星期\S[ \t]+([^\s]+)", raw)
    names = str.maketrans(
        {"驚": "惊", "蟄": "蛰", "穀": "谷", "滿": "满", "種": "种", "處": "处"}
    )
    published = {
        name.translate(names): (int(month), int(day)) for month, day, name in rows
    }
    assert len(published) == 24
    month_starts = {
        "小寒": "丑",
        "立春": "寅",
        "惊蛰": "卯",
        "清明": "辰",
        "立夏": "巳",
        "芒种": "午",
        "小暑": "未",
        "立秋": "申",
        "白露": "酉",
        "寒露": "戌",
        "立冬": "亥",
        "大雪": "子",
    }
    for term in get_solar_terms_for_year(2026):
        assert (term.moment.month, term.moment.day) == published[term.name]
        if term.name in month_starts:
            before = BaZiCalendar.get_four_pillars(
                term.moment - timedelta(microseconds=1), timezone_name="Asia/Shanghai"
            )
            at = BaZiCalendar.get_four_pillars(
                term.moment, timezone_name="Asia/Shanghai"
            )
            assert at["month"][1] == month_starts[term.name]
            assert at["month"] != before["month"]
