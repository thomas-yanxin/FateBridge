"""Current discrete-palace pattern inputs, source conditions and public output."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.guolao import guolao, guolao_moira
from fatebridge.core.guolao.guolao_moira_native import (
    MoiraNativeProvider,
    native_source_facts,
)
from fatebridge.core.guolao.guolao_moira_provider import (
    MoiraCalendarFacts,
    MoiraGodPlacement,
    MoiraMansionAnchor,
    MoiraMansionBoundaries,
    MoiraProviderProfile,
    MoiraProviderResolution,
    resolve_source_provider_facts,
)
from fatebridge.core.guolao.guolao_moira_rules import (
    CompiledProfile,
    MoiraSourceFacts,
    evaluate_source_profile,
    load_source_profile,
    pattern_records,
)
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.support.transports import SPECS, business, rest, surface_calls

_FIXTURE = Path(__file__).resolve().parents[1] / "data/guolao/moira_palace_inputs.json"


@pytest.fixture(scope="module")
def moira_cases():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.local_data
def test_oracle_fixture_is_nonempty(moira_cases) -> None:
    assert moira_cases, "guolaoMoira oracle fixture must contain cases"


@pytest.mark.local_data
def test_good_patterns_sort_before_bad(moira_cases) -> None:
    """build order: good first, bad after (matches JS level sort)."""
    for case in moira_cases:
        patterns = guolao_moira.calculate(case["facts"])
        ranks = [0 if p["level"] == "good" else 1 for p in patterns]
        assert ranks == sorted(ranks), case["label"]


@pytest.mark.local_data
def test_god_dependent_patterns_inert_without_gods(moira_cases) -> None:
    """日月拱贵人 / 命登岁驾 stay inert when 神煞 positions are absent (oracle cases)."""
    for case in moira_cases:
        names = {p["name"] for p in guolao_moira.calculate(case["facts"])}
        assert "日月拱贵人" not in names
        assert "命登岁驾" not in names


def test_purple_clouds_matches_horosa_fixtures() -> None:
    """紫炁(木余) horosa 对照锁：4 张 horosa 七政四余盘 fixture 的紫炁黄经，残差 <0.01°。"""
    # (JD_UT, horosa Purple Clouds 黄经) —— chart_guolao / 1998_predictive / liureng / traditional
    horosa_points = [
        (2446145.583333333, 358.66910331920116),
        (2450865.033333333, 164.80172577759032),
        (2461135.054166667, 166.32382978206476),
        (2461193.770833333, 168.39076),
    ]
    for jd, expected in horosa_points:
        got = guolao_moira.purple_clouds_longitude(jd)
        delta = ((got - expected + 180) % 360) - 180
        assert (
            abs(delta) < 0.01
        ), f"jd={jd}: 紫炁 {got} vs horosa {expected} (Δ={delta})"


def test_purple_clouds_matches_pinned_horosa_source_controls() -> None:
    # Actual pcLon execution at10fb75de, kept independently of FateBridge.
    # https://github.com/Horace-Maxwell/Horosa-Web-App-comprehensively-improved-MacOS/blob/10fb75de980bb0a6e0d1f50c7ee93cc97a88d7de/Horosa-Web/flatlib-ctrad2/flatlib/ephem/tools.py
    controls = [
        (1721425.5, 47.29638140791576),
        (2415020.5, 343.0135251475258),
        (2451544.5, 188.7201016913959),
        (5373449.5, 84.71819983005116),
    ]
    for jd, expected in controls:
        assert guolao_moira.purple_clouds_longitude(jd) == expected


def test_si_yu_sign_index_matches_horosa_chart() -> None:
    """四余(孛/罗/计/炁) horosa 对照锁：chart_guolao fixture(1985-03-21 10:00 +08 上海)。

    horosa 后端实测：孛 Aries(0)、罗 Taurus(1)、计 Scorpio(7)、炁 Pisces(11)。
    """

    guolao = calculate_core_chart_analysis(
        birth_year=1985,
        birth_month=3,
        birth_day=21,
        birth_hour=10,
        birth_minute=0,
        birth_longitude=121.47,
        birth_latitude=31.22,
        chart_variant="guolao_chart",
        birth_timezone="Asia/Shanghai",
    )["guolao"]
    assert guolao["si_yu_sign_index"] == {"孛": 0, "罗": 1, "计": 7, "炁": 11}


def test_gu_yue_du_ming_counts_purple_clouds() -> None:
    """孤月独明：紫炁补齐后，同宫计数覆盖全 11 体——炁与月同宫应使月不再「独居」。"""
    base = {
        "日": 1,
        "月": 5,
        "水": 2,
        "金": 3,
        "火": 7,
        "木": 8,
        "土": 9,
        "孛": 10,
        "罗": 0,
        "计": 6,
    }
    # 月独居（炁不在月宫）→ 点亮
    alone = guolao_moira.calculate(
        {
            "asc_lon": 75,
            "planet_signidx": {**base, "炁": 4},
            "is_day": False,
            "is_winter": False,
        }
    )
    assert any(p["name"] == "孤月独明" for p in alone)
    # 炁与月同宫(5) → 月不再独居 → 不点亮
    with_qi = guolao_moira.calculate(
        {
            "asc_lon": 75,
            "planet_signidx": {**base, "炁": 5},
            "is_day": False,
            "is_winter": False,
        }
    )
    assert not any(p["name"] == "孤月独明" for p in with_qi)


@pytest.mark.parametrize(
    "day,winter,expected",
    [
        (False, False, [("孤月独明", "good")]),
        (False, True, [("寒月单行", "bad")]),
        (True, False, []),
        (True, True, [("寒月单行", "good")]),
        (None, True, []),
        (False, None, []),
    ],
)
def test_moon_solitude_matches_original_moira_seasonal_rules(
    day: bool | None, winter: bool | None, expected
) -> None:
    # Executed unmodified Moira1.50Final RuleEntry/RuleParse and three original
    # moon rules at9bb126fd. Its winter-night rule rejects the generic good one.
    planets = dict(zip("日月金木水火土计罗炁孛", range(11)))
    patterns = guolao_moira.calculate(
        {
            "planet_signidx": planets,
            "life_sign_idx": 0,
            "god_signidx": {"岁驾": 0},
            "is_day": day,
            "is_winter": winter,
        }
    )
    levels = [p["level"] != "good" for p in patterns]
    assert levels == sorted(levels)
    assert any(p["name"] == "命登岁驾" for p in patterns)
    moon = [p for p in patterns if p["name"] in {"孤月独明", "寒月单行"}]
    assert [(p["name"], p["level"]) for p in moon] == expected
    for pattern in moon:
        assert pattern["source"].endswith(
            "9bb126fd84997aa26fed6e91b4bdf438fceb0e38/moira_s.prop"
        )
        assert pattern["evidence"]["inputs"]["is_winter"] is winter


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("hour,level", [(0, "bad"), (12, "good")])
def test_cold_moon_rule_reaches_all_three_transports(
    tool: str, hour: int, level: str, surface_calls
) -> None:
    # Synthetic J2000 date, selected after confirming all11positions and the
    # actual solar conditions. This checks source rule composition/delivery,
    # not independent absolute astronomy or prediction efficacy.
    inputs = {
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": hour,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 51.5,
    }
    if tool == "astro_chart":
        inputs["chart_variant"] = "guolao_chart"
    else:
        pass
    fields = [
        "guolao.moira_patterns",
        "guolao.conditions",
        "guolao.profile.pattern_model_id",
        "guolao.rule_trace",
    ]
    response, protocol, code, cli = surface_calls(
        SPECS[tool],
        inputs,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    outputs = [response.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    result = outputs[0]["guolao"]
    assert result["conditions"]["season"] == "冬"
    assert result["conditions"]["is_day"] == (hour == 12)
    patterns = result["moira_patterns"]
    moon = [p for p in patterns if p["name"] in {"孤月独明", "寒月单行"}]
    assert [(p["name"], p["level"]) for p in moon] == [("寒月单行", level)]
    assert not moon[0]["classical_acceptance"]
    trace = next(
        t
        for t in result["rule_trace"]
        if t["rule_id"] == "moira_conditions_with_seasonal_moon_v3"
    )
    witness = next(
        p for p in trace["outputs"]["matched_patterns"] if p["name"] == "寒月单行"
    )
    assert witness["source"] == moon[0]["source"]


def test_god_patterns_fire_when_positions_supplied() -> None:
    """供入神煞位置时，日月拱贵人 / 命登岁驾 应能点亮（Phase 2a）。"""
    # 命登岁驾：显式命宫与岁驾同宫。
    dengsuijia = guolao_moira.calculate(
        {"life_sign_idx": 6, "planet_signidx": {}, "god_signidx": {"岁驾": 6}}
    )
    assert any(p["name"] == "命登岁驾" for p in dengsuijia)

    # 日月拱贵人（昼取天贵）：日=天贵+4、月=天贵-4。
    gongguiren = guolao_moira.calculate(
        {
            "life_sign_idx": 3,
            "planet_signidx": {"日": 4, "月": 8},
            "god_signidx": {"天贵": 0},
            "is_day": True,
        }
    )
    assert any(p["name"] == "日月拱贵人" for p in gongguiren)


@pytest.mark.local_data
def test_section_text_format(moira_cases) -> None:
    """build_section_text mirrors runGuolaoMoira: 喜格/忌格 lines, 名（detail）；-joined."""
    # multi-fire case is index 0
    patterns = guolao_moira.calculate(moira_cases[0]["facts"])
    text = guolao_moira.build_section_text(patterns)
    lines = text.split("\n")
    assert lines[0].startswith("喜格：")
    assert lines[1].startswith("忌格：")
    assert "金水相涵" in lines[0]
    assert "孛犯太阳" in lines[1]
    assert "；" in lines[1]  # multiple 忌格 joined


def test_empty_chart_yields_no_patterns() -> None:
    """A chart with no usable positions produces empty 喜格/忌格 (not a crash)."""
    patterns = guolao_moira.calculate({"asc_lon": None, "planet_signidx": {}})
    assert patterns == []
    assert guolao_moira.build_section_text(patterns) == "喜格：（无）\n忌格：（无）"


@pytest.mark.parametrize(
    "case_id",
    ["G01", "G02", "G03", "G04", "G05", "G06", "U01", "U02", "U03", "U04"],
)
def test_original_java_synthetic_rule_mechanisms(case_id: str, tmp_path: Path) -> None:
    """Frozen author-engine states, not the full298-rule source profile.

    The lowercase controls exercise priority, false-intermediary rejection,
    hidden references and both recursion kinds. Uppercase source references
    retain their original undefined-symbol behavior. No oracle is rerun here.
    """

    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/guolao/moira_rule_semantics_v1.json"
        ).read_text(encoding="utf-8")
    )
    case = next(row for row in fixture["cases"] if row["id"] == case_id)
    original_facts = case["original_input_facts"]
    booleans = {
        name[1:]: value == "t"
        for name, value in original_facts.items()
        if name.startswith("?")
    }
    strings = {
        name[1:]: tuple(value) if isinstance(value, list) else value
        for name, value in original_facts.items()
        if name.startswith("$")
    }
    profile_path = tmp_path / "synthetic-source-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile_id": "synthetic_original_java_mechanism_control",
                "source_commit": fixture["source"]["commit"],
                "source_property_sha256": case["dsl_sha256"],
                "source_url": fixture["source"]["java_sources"]["RuleEntry.java"][
                    "url"
                ],
                "separator": "、",
                "full_zodiac": [],
                "full_stellar_signs": [],
                "primitive_booleans": sorted(booleans),
                "source_strings": {},
                "declarations": [
                    {"line": index, "text": text}
                    for index, text in enumerate(case["dsl"].splitlines(), 1)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    profile = load_source_profile(profile_path)
    assert list(profile.evaluation_order) == case["expected"]["outer_evaluation_order"]
    evaluation = evaluate_source_profile(
        MoiraSourceFacts(
            strings=strings,
            booleans=booleans,
            male=case["male"],
        ),
        profile=profile,
        display_level=case["display_level"],
        fill_max_styles=case["fill_max_styles"],
    )
    records = {row["rule_id"]: row for row in evaluation.to_record()["rules"]}
    assert set(records) == set(case["expected"]["states"])
    for rule_id, original in case["expected"]["states"].items():
        current = original["tag_is_current"]
        expected = {
            "evaluated": original["evaluated"] if current else False,
            "result": original["result"] if current else None,
            "valid": original["valid"] if current else False,
            "hidden": original["hidden"] if current else False,
        }
        actual = records[rule_id]
        assert {
            "evaluated": actual["raw_state"] == "computed",
            "result": actual["value"],
            "valid": actual["condition_value"] is True,
            "hidden": actual["hidden"],
        } == expected, (case_id, rule_id)
    patterns = pattern_records(evaluation)
    assert [row["name"] for row in patterns if row["level"] == "good"] == case[
        "expected"
    ]["good"]
    assert [row["name"] for row in patterns if row["level"] == "bad"] == case[
        "expected"
    ]["bad"]


@pytest.fixture
def synthetic_moira_provider_profile():
    """Small invented resources; no original provider tables or star catalogue.

    Ordering follows ChartData.getStarSigns/addStarSign at Moira1.50Final
    9bb126fd84997aa26fed6e91b4bdf438fceb0e38. The arbitrary placements below
    isolate that operator without claiming historical or astronomical facts.
    """

    zodiac = tuple("戌酉申未午巳辰卯寅丑子亥")
    stages = tuple(f"生{index:02d}" for index in range(12))
    stems = tuple("甲乙丙丁戊己庚辛壬癸")
    return MoiraProviderProfile(
        profile_id="synthetic_provider_operators",
        source_commit="synthetic-operator-source",
        source_property_sha256="0" * 64,
        source_url="https://example.invalid/synthetic-provider",
        full_zodiac=tuple(branch + "宫" for branch in zodiac),
        zodiac=zodiac,
        twelve_signs=zodiac[1:] + zodiac[:1],
        bodies=("日", "月", "水"),
        anchors=tuple(
            MoiraMansionAnchor(f"synthetic-{index}", f"m{index:02d}", 0.0)
            for index in range(28)
        ),
        corrections={},
        selected_gods=(
            "年神",
            "月神",
            "时神",
            "同神",
            "别名",
            "组子",
            "生00",
            "停用",
            "缺位",
        ),
        year_names=("甲子",),
        stems=stems,
        branches=tuple("子丑寅卯辰巳午未申酉戌亥"),
        year_data={"甲子": ("合成元",)},
        long_life_index=0,
        long_life_starts={"合成元": 0},
        long_life_stages=stages,
        year_gods={
            "甲子": (
                MoiraGodPlacement("酉", "同神"),
                MoiraGodPlacement("戌", "同神"),
                MoiraGodPlacement("戌", "父组"),
                MoiraGodPlacement("戌", "停用"),
                MoiraGodPlacement("寅", "年神"),
            ),
        },
        stem_gods={"甲": ()},
        branch_gods={"子": ()},
        month_gods={"寅": (MoiraGodPlacement("卯", "月神"),)},
        month_hour_gods={"寅午": (MoiraGodPlacement("辰", "时神"),)},
        qi_name="合成气",
        qi_seeds={stem: ("戌", "戌") for stem in stems},
        groups={"父组": ("+组子",)},
        master_defaults={
            **dict.fromkeys(stages, False),
            "生00": True,
            "父组": False,
            "停用": False,
            "合成气": False,
        },
        paired_gods=(("同神", "别名"),),
        god_requirements={
            "年神": ("year_pillar",),
            "月神": ("month_pillar",),
            "时神": ("month_pillar", "hour_branch"),
            "同神": ("year_pillar",),
            "别名": ("year_pillar",),
            "组子": ("year_pillar",),
            "生00": ("year_pillar",),
            "停用": (),
            "缺位": (),
        },
        seasons=("春", "夏", "秋", "冬"),
        lunar_faces=(("合成暗月", 28, 2), ("合成半月", 7, 9)),
    )


@pytest.mark.parametrize(
    "query_kind,expected_mansion,expected_near",
    [
        ("previous_float", "m25", True),
        ("boundary", "m26", True),
        ("minus_one", "m25", False),
        ("plus_one", "m26", False),
        ("inside_minus_one", "m25", True),
        ("inside_plus_one", "m26", True),
    ],
)
def test_source_provider_exact_circle_and_strict_mansion_boundary(
    synthetic_moira_provider_profile,
    query_kind: str,
    expected_mansion: str,
    expected_near: bool,
) -> None:
    """Exact supplied-value policy, including the rounded-wrap failure shape.

    The independent R24 integer reference preserved both original Java invalid
    labels separately. These invented coordinates test the selected circle
    operator, not the historical catalogue or a new astronomical reference.
    """

    boundary = Fraction(1, 2**20)
    query = {
        "previous_float": math.nextafter(float(boundary), -math.inf),
        "boundary": boundary,
        "minus_one": boundary - 1,
        "plus_one": boundary + 1,
        "inside_minus_one": boundary - 1 + Fraction(1, 2**60),
        "inside_plus_one": boundary + 1 - Fraction(1, 2**60),
    }[query_kind]
    points = tuple(Fraction(16 + 13 * index) for index in range(26)) + (
        boundary,
        Fraction(10),
    )
    result = resolve_source_provider_facts(
        profile=synthetic_moira_provider_profile,
        calendar=MoiraCalendarFacts(),
        longitudes={"日": query, "月": query},
        is_day=None,
        mansion_boundaries=MoiraMansionBoundaries(points),
    )
    assert dict(result.facts.mansions) == {
        "日": expected_mansion,
        "月": expected_mansion,
        "身": expected_mansion,
    }
    for name in ("日", "月", "身"):
        assert result.facts.booleans[name + "宿歧"] is expected_near
        assert "%" + name not in result.facts.unavailable
    assert "%水" in result.facts.unavailable
    assert "?水宿歧" in result.facts.unavailable
    assert "命" not in result.facts.mansions
    assert "%命" in result.facts.unavailable
    assert "?命宿歧" in result.facts.unavailable


def test_source_provider_god_scan_groups_aliases_and_long_life_order(
    synthetic_moira_provider_profile,
) -> None:

    result = resolve_source_provider_facts(
        profile=synthetic_moira_provider_profile,
        calendar=MoiraCalendarFacts(
            year_pillar="甲子",
            month_pillar="丙寅",
            hour_branch="午",
            lunar_day=1,
        ),
        longitudes={},
        is_day=None,
    )
    # The final palace scan visits 戌 before 酉, despite reversed head insertion.
    assert dict(result.facts.palaces) == {
        "年神": "寅宫",
        "月神": "卯宫",
        "时神": "辰宫",
        "同神": "酉宫",
        "别名": "酉宫",
        "组子": "戌宫",
        "生00": "酉宫",
    }
    assert result.known_absent == ("@停用", "@缺位")
    assert not any(key.startswith("@") for key in result.facts.unavailable)
    assert result.facts.strings["月柱"] == "丙寅"
    assert {name: result.facts.booleans[name] for name in "春夏秋冬"} == {
        "春": True,
        "夏": False,
        "秋": False,
        "冬": False,
    }
    assert result.facts.booleans["合成暗月"] is True
    assert result.facts.booleans["合成半月"] is False


@pytest.mark.parametrize("calendar_kind", ["year_only", "month_hour_only"])
def test_source_provider_partial_calendar_keeps_known_and_absent_distinct(
    synthetic_moira_provider_profile, calendar_kind: str
) -> None:

    if calendar_kind == "year_only":
        calendar = MoiraCalendarFacts(year_pillar="甲子")
        expected = {
            "年神": "寅宫",
            "同神": "酉宫",
            "别名": "酉宫",
            "组子": "戌宫",
            "生00": "酉宫",
        }
        unknown = {"@月神", "@时神"}
    else:
        calendar = MoiraCalendarFacts(month_pillar="丙寅", hour_branch="午")
        expected = {"月神": "卯宫", "时神": "辰宫"}
        unknown = {"@年神", "@同神", "@别名", "@组子", "@生00"}
    result = resolve_source_provider_facts(
        profile=synthetic_moira_provider_profile,
        calendar=calendar,
        longitudes={},
        is_day=None,
    )
    assert dict(result.facts.palaces) == expected
    assert {key for key in result.facts.unavailable if key.startswith("@")} == unknown
    assert result.known_absent == ("@停用", "@缺位")
    assert set(result.known_absent).isdisjoint(result.facts.unavailable)
    assert all(key[1:] not in result.facts.palaces for key in unknown)


def test_native_source_provider_replaces_known_unknown_and_absent_without_luwei_mutation() -> (
    None
):

    names = tuple("日月金木水火土计罗炁孛")
    longitudes = {name: 15.0 + 30 * index for index, name in enumerate(names)}
    palaces = {name: index for index, name in enumerate(names)}
    luwei = {"天贵": 0, "玉贵": 1, "岁驾": 2}
    premises = dict(
        longitudes=longitudes,
        palace_indices=palaces,
        life_sign_index=3,
        god_sign_indices=luwei,
        is_day=True,
        season="冬",
    )
    baseline = native_source_facts(**premises)
    replacement = MoiraProviderResolution(
        MoiraSourceFacts(
            palaces={"天贵": "亥木", "斗杓": "子土"},
            mansions={"日": "合成宿"},
            strings={"月柱": "合成月"},
            booleans={"春": True, "晦朔": True},
            unavailable={
                "@玉贵": "Missing source year",
                "?冬": "Missing source season",
            },
            provenance={"synthetic_source": "explicit replacement"},
        ),
        known_absent=("@岁驾",),
    )
    merged = native_source_facts(**premises, source_provider=replacement)
    assert baseline.palaces["天贵"] == "戌火"
    assert baseline.palaces["玉贵"] == "酉金"
    assert baseline.palaces["岁驾"] == "申水"
    assert baseline.booleans["冬"] is True
    assert merged.palaces["天贵"] == "亥木"
    assert merged.palaces["斗杓"] == "子土"
    assert "@斗杓" not in merged.unavailable
    assert "玉贵" not in merged.palaces
    assert merged.unavailable["@玉贵"] == "Missing source year"
    assert "岁驾" not in merged.palaces
    assert "@岁驾" not in merged.unavailable
    assert merged.mansions["日"] == "合成宿"
    assert "%日" not in merged.unavailable
    assert merged.strings["月柱"] == "合成月"
    assert "$月柱" not in merged.unavailable
    assert merged.booleans["春"] is True
    assert merged.booleans["晦朔"] is True
    assert "?晦朔" not in merged.unavailable
    assert "冬" not in merged.booleans
    assert merged.unavailable["?冬"] == "Missing source season"
    assert merged.palaces["命"] == baseline.palaces["命"]
    assert merged.palaces["身"] == baseline.palaces["月"]
    assert merged.unavailable["%命"] == baseline.unavailable["%命"]
    assert merged.provenance["synthetic_source"] == "explicit replacement"
    assert luwei == {"天贵": 0, "玉贵": 1, "岁驾": 2}
    assert native_source_facts(**premises) == baseline


@pytest.mark.parametrize(
    "mismatch", ["missing_rule_profile", "different_commit", "different_property"]
)
def test_source_provider_preflight_rejects_before_positions(
    synthetic_moira_provider_profile, monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:

    profile = synthetic_moira_provider_profile
    rule_profile = CompiledProfile(
        profile_id="synthetic_rule_profile",
        source_commit=profile.source_commit,
        source_property_sha256=profile.source_property_sha256,
        source_url=profile.source_url,
        source_declarations=0,
        rules=(),
        aliases=(),
        evaluation_order=(),
        full_zodiac=(),
        full_stellar_signs=(),
        primitive_booleans=(),
        source_strings=(),
        separator="、",
    )
    if mismatch == "missing_rule_profile":
        rule_profile = None
        message = "显式源规则profile"
    else:
        rule_profile = replace(
            rule_profile,
            **{
                (
                    "source_commit"
                    if mismatch == "different_commit"
                    else "source_property_sha256"
                ): "different-synthetic-source",
            },
        )
        message = "同一已声明源版本"
    clock = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    birth = AstroBirthInfo(
        name="Synthetic preflight",
        birth_place="Synthetic",
        timezone="UTC",
        longitude=0.0,
        latitude=0.0,
        local_datetime=clock,
        utc_datetime=clock,
    )

    def unexpected_positions(*args, **kwargs):
        pytest.fail("Provider preflight must reject before native positions")

    monkeypatch.setattr(guolao, "positions", unexpected_positions)
    # Isolate the actual builder preflight from the native source-session wrapper.
    with pytest.raises(ValueError, match=message):
        guolao.build_chart.__wrapped__(
            birth,
            moira_profile=rule_profile,
            moira_provider=MoiraNativeProvider(profile),
        )
