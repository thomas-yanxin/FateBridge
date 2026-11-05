"""Corrected numerology facts and evidence agree across REST, MCP and CLI."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.cli import run as cli_run
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    projected_outputs,
)
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.support.heluo_source_facts import (
    COMMENTARY_RULESET_ID,
    HEADER_COUNT,
    PENDING_COUNT,
)

rest = shared_rest

INPUT = dict(
    date="2026-06-21",
    time="16:30:00",
    zone="Asia/Shanghai",
    gender="女",
    use_true_solar_time=False,
)


@pytest.mark.parametrize(
    "date,phase_index,gua,najia_present,month_match",
    [
        ("1998-02-26", 0, "雷水解", True, False),
        ("1998-03-13", 1, "雷水解", True, False),
        ("1998-03-14", 1, "風水渙", True, False),
        ("2000-04-19", 0, "水風井", False, True),
    ],
)
@pytest.mark.parametrize("phases_only", [False, True])
def test_heluo_month_najia_separate_facts_on_three_surfaces(
    date,
    phase_index,
    gua,
    najia_present,
    month_match,
    phases_only,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": "男"}
    fields = (
        ["judge.month_affinity.phases"]
        if phases_only
        else [
            "judge.month_affinity",
            "judge.najia",
            "judge.deSheng",
            "numerology_evidence.rule_trace",
            "snapshot_text",
        ]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        affinity = output["judge"]["month_affinity"]
        row = affinity["phases"][phase_index]
        clause = row["natal_najia_clause"]
        assert clause["month_label_match"] is month_match
        assert clause["najia"]["present"] is najia_present
        assert clause["match"] is None and "match" in clause
        assert clause["connector_status"] == "source_ji_scope_unresolved"
        assert clause["najia"]["matches"] == (
            [{"pos": 1, "kind": "direct"}] if najia_present else []
        )
        if not phases_only:
            assert (
                row["gua"] == gua and affinity["registered_natal_najia_clauses"] == 13
            )
            assert output["judge"]["deSheng"] is any(
                r["present"] for r in output["judge"]["najia"]
            )
            assert clause["najia"] == {
                k: output["judge"]["najia"][phase_index][k]
                for k in ("phase", "gua", "year_ganzhi", "matches", "present")
            }
            assert all(
                w["match"] is None for w in row["additional_windows"] if w["qualifiers"]
            )
            trace = next(
                t
                for t in output["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == affinity["ruleset_id"]
            )
            assert trace["facts"] == affinity
            assert "及字连接范围待核，整条条件未定" in output["snapshot_text"]
            assert (
                "月号匹配，附加条件待核" if month_match else "月号不匹配，附加条件待核"
            ) in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,phase_index,gua,matches,basis,page",
    [
        (
            "1980-03-02",
            "09:33:00",
            1,
            "雷水解",
            [{"pos": 5, "kind": "direct"}],
            "pure_trigram_rule",
            240,
        ),
        (
            "1998-03-14",
            "09:33:00",
            1,
            "風水渙",
            [{"pos": 1, "kind": "direct"}],
            "hexagram_entry",
            260,
        ),
        (
            "2000-05-11",
            "01:30",
            0,
            "水雷屯",
            [{"pos": 3, "kind": "direct"}],
            "hexagram_entry",
            124,
        ),
        ("2026-11-12", "09:33:00", 1, "震為雷", [], "hexagram_entry", 240),
    ],
)
@pytest.mark.parametrize("minimal", [False, True])
def test_heluo_najia_sources_and_printed_order_issue_on_three_surfaces(
    date, time, phase_index, gua, matches, basis, page, minimal, rest, tmp_path, capsys
):
    import hashlib

    from fatebridge.core.heluo_najia import COLLATION_PATH

    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": time, "gender": "男"}
    fields = (
        [
            "judge.najia",
            "numerology_evidence.najia_collation.pure_trigram_tables",
            "numerology_evidence.najia_collation.complete_assessment",
        ]
        if minimal
        else evidence_views(spec)["najia"]["fields"]
        + ["snapshot_text", "numerology_evidence.rule_trace", "judge.month_affinity"]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        summary = out["numerology_evidence"]["najia_collation"]
        assert (
            summary["pure_trigram_tables"] == 8
            and summary["complete_assessment"] is False
        )
        row = out["judge"]["najia"][phase_index]
        assert row["gua"] == gua and row["matches"] == matches
        assert all(e["source"]["basis"] == basis for e in row["lines"])
        pos = matches[0]["pos"] if matches else 1
        assert row["lines"][pos - 1]["source"]["source_pdf_page"] == page
        if gua == "雷水解":
            issue = row["source_issues"][0]
            assert (
                len(issue["witnesses"]) == 2
                and issue["ordinal_list_semantics_resolved"] is False
            )
            assert issue["literal_najia_list"] != issue["rule_derived_positional_list"]
            assert set(issue["literal_najia_list"]) == set(
                issue["rule_derived_positional_list"]
            )
        else:
            assert row["source_issues"] == []
        if not minimal:
            assert (
                summary["directly_collated_hexagrams"] == 13
                and summary["other_hexagrams_not_individually_collated"] == 51
            )
            assert (
                summary["pure_table_assignment_slots"] == 48
                and summary["pure_table_borrowed_slots"] == 12
            )
            assert (
                summary["direct_assignment_observations"] == 78
                and summary["borrowed_assignment_observations"] == 18
            )
            assert (
                summary["sha256"]
                == hashlib.sha256(COLLATION_PATH.read_bytes()).hexdigest()
            )
            assert (
                summary["unquantified_timing_najia_clauses"][0]["month_numbers"] is None
            )
            trace = next(
                t
                for t in out["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == "year_najia_at_actual_line_positions"
            )
            assert trace["facts"]["phases"] == out["judge"]["najia"]
            if gua == "雷水解":
                assert "计算第5爻正纳" in out["snapshot_text"]
                assert "两印本原文列举末两支顺序" in out["snapshot_text"]
            assert out["judge"]["month_affinity"]["collation_version"] == "2.2.0"
            if gua == "震為雷":
                clause = out["judge"]["month_affinity"]["phases"][phase_index][
                    "natal_najia_clause"
                ]
                assert (
                    clause["literal"] == "如生於十月及納甲者"
                    and clause["month_label_match"] is True
                )
                assert clause["najia"]["present"] is False and clause["match"] is None


def test_canping_unresolved_header_leaves_project_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": "1994-06-03", "time": "17:30", "gender": "女"}
    prefix = "benming.verses.selectionShun"
    fields = [
        f"{prefix}.body_reading_status",
        f"{prefix}.number_attribution_status",
        f"{prefix}.number_reading_evidence.observed_header",
        f"{prefix}.number_reading_evidence.resolution_status",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    expected = {
        "body_reading_status": "source_body_printed_blank",
        "number_attribution_status": "provisional_inherited_key",
        "number_reading_evidence": {
            "observed_header": "□□四八",
            "resolution_status": "unresolved",
        },
    }
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["benming"]["verses"] == {"selectionShun": expected}
        assert "snapshot_text" not in output


@pytest.mark.parametrize(
    "date,time,names,positions,matches",
    [
        ("2000-05-10", "01:30", ["水山蹇", "山地剝"], [5, 2], [False, False]),
        ("2000-05-11", "05:30", ["乾為天", "風天小畜"], [1, 4], [False, True]),
        ("2000-05-11", "23:30", ["水地比", "坤為地"], [5, 2], [True, False]),
    ],
)
def test_heluo_actual_phase_line_conditions_on_three_surfaces(
    date, time, names, positions, matches, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": time, "gender": "男"}
    fields = evidence_views(spec)["line_conditions"]["fields"] + ["snapshot_text"]
    assert "judge.line_conditions" in fields
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        evidence = output["judge"]["line_conditions"]
        assert [r["gua"] for r in evidence["phases"]] == names
        assert [r["pos"] for r in evidence["phases"]] == positions
        assert [r["zhongzong"]["match"] for r in evidence["phases"]] == matches
        for row in evidence["phases"]:
            assert row["lines"] == output["chart"][row["phase"]]["lines"]
            assert row["pos"] == output["chart"][row["phase"]]["yuan"]
        assert (
            next(
                r["facts"]
                for r in output["numerology_evidence"]["rule_trace"]
                if r["rule_id"] == evidence["ruleset_id"]
            )
            == evidence
        )
        assert evidence["ten_condition_score"] is None
        assert evidence["source_dangwei"]["match"] is None
        assert "[爻位条文条件]" in output["snapshot_text"]
        assert "元堂：当位" not in output["snapshot_text"]
        assert "元堂：不当位" not in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,matches",
    [
        ("1990-06-15", "09:33", [True, False]),
        ("2000-05-11", "05:30", [False, True]),
        ("2000-05-11", "23:30", [False, False]),
        ("2000-05-10", "01:30", [False, False]),
    ],
)
@pytest.mark.parametrize("phases_only", [False, True])
def test_heluo_source_youyuan_actual_phase_facts_on_three_surfaces(
    date, time, matches, phases_only, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": time, "gender": "男"}
    fields = (
        [
            "chart.xian",
            "chart.hou",
            "judge.line_conditions.phases",
            "judge.yuanTang",
            "numerology_evidence.rule_trace",
        ]
        if phases_only
        else evidence_views(spec)["line_conditions"]["fields"]
    ) + ["snapshot_text"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        evidence = output["judge"]["line_conditions"]
        rows = evidence["phases"]
        assert [r["source_youyuan"]["clause_match"] for r in rows] == matches
        trace = next(
            t["facts"]
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == "heluo_wenming_line_conditions_v1"
        )
        assert rows == trace["phases"]
        for row in rows:
            chart = output["chart"][row["phase"]]
            aid = row["source_youyuan"]
            assert aid["selected_pos"] == chart["yuan"] == row["pos"]
            assert aid["selected_yang"] == bool(chart["lines"][chart["yuan"] - 1])
            assert aid["corresponding_pos"] == (
                chart["yuan"] + 3 if chart["yuan"] <= 3 else chart["yuan"] - 3
            )
            assert aid["corresponding_yang"] == bool(
                chart["lines"][aid["corresponding_pos"] - 1]
            )
            assert aid["polarity_opposed"] == (
                aid["selected_yang"] != aid["corresponding_yang"]
            )
        assert "先天元堂与应爻阴阳" in output["snapshot_text"]
        assert "先天有援原句（主本阴爻读法）" in output["snapshot_text"]
        assert "后天有援原句（主本阴爻读法）" in output["snapshot_text"]
        assert "非十体有援总判" in output["snapshot_text"]
        assert (
            output["judge"]["yuanTang"]["youYing"]
            is rows[0]["source_youyuan"]["polarity_opposed"]
        )


def test_heluo_line_conditions_view_in_real_mcp_without_snapshot():
    spec = SPECS["heluo"]
    result = asyncio.run(
        native(
            spec,
            {
                **INPUT,
                "fields": evidence_views(spec)["line_conditions"]["fields"],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error and "snapshot_text" not in result.structured_content
    assert "line_conditions" in result.structured_content["judge"]


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "zone,utc,hour",
    [
        ("__omitted__", "1990-06-15T01:30:00+00:00", "巳"),
        (None, "1990-06-15T01:30:00+00:00", "巳"),
        ("+08:00", "1990-06-15T01:30:00+00:00", "巳"),
        ("Asia/Shanghai", "1990-06-15T00:30:00+00:00", "辰"),
        (" Asia/Shanghai ", "1990-06-15T00:30:00+00:00", "辰"),
        ("+09:00", "1990-06-15T00:30:00+00:00", "辰"),
    ],
)
def test_numerology_default_and_historical_zone_on_three_surfaces(
    key, zone, utc, hour, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = dict(
        date="1990-06-15",
        time="09:30",
        gender="男",
        lon="120",
        use_true_solar_time=True,
    )
    if zone != "__omitted__":
        payload["zone"] = zone
    fields = [
        "input_normalized",
        "four_pillars",
        "numerology_evidence.birth_clock",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        clock = output["numerology_evidence"]["birth_clock"]
        assert clock["birth_instant_utc"] == utc
        assert output["four_pillars"]["hour"]["branch"] == hour
        assert clock["timezone_spec"] == output["input_normalized"]["zone"]
        assert clock["timezone_spec"] in output["snapshot_text"]
        assert "固定+08:00，不推定出生地" in output["snapshot_text"]
        assert (
            next(
                t["facts"]
                for t in output["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == clock["policy_id"]
            )
            == clock
        )


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "date,time,zone,status,error",
    [
        ("1990-06-15", "09:30", " ", 422, "zone"),
        ("1990-06-15", "09:30", "UTC+08:90", 422, "zone"),
        ("1990-04-15", "02:30", "Asia/Shanghai", 400, "nonexistent local time"),
        ("1990-09-16", "01:30", "Asia/Shanghai", 400, "ambiguous local time"),
    ],
)
def test_numerology_blank_invalid_and_indeterminate_zone_on_three_surfaces(
    key, date, time, zone, status, error, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**INPUT, "date": date, "time": time, "zone": zone}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == status and code != 0 and protocol.is_error
    assert error in str(response.json())
    assert error in str(local)
    assert error in str(protocol.content)


@pytest.mark.parametrize(
    "date,time,gender,number,page,state,pair",
    [
        (
            "1996-06-16",
            "21:30:00",
            "女",
            2449,
            72,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1996-06-08",
            "03:30:00",
            "男",
            2332,
            65,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1996-06-09",
            "09:30:00",
            "男",
            2536,
            67,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1996-06-14",
            "15:30:00",
            "女",
            2344,
            71,
            "source_printed_partial_blank",
            "shun_only",
        ),
        (
            "1996-06-08",
            "15:30:00",
            "女",
            2938,
            66,
            "source_reading_uncertain",
            "both_directions",
        ),
        (
            "1990-06-12",
            "15:30:00",
            "男",
            3373,
            104,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "1994-06-07",
            "13:30:00",
            "FEMALE",
            2838,
            74,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "1994-06-08",
            "05:30:00",
            "女",
            2335,
            74,
            "source_printed_blank",
            "neither_direction",
        ),
        (
            "1996-06-08",
            "01:30:00",
            "女",
            2231,
            65,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "2000-06-02",
            "21:30",
            "女",
            2920,
            93,
            "source_printed_partial_blank",
            "both_directions",
        ),
        (
            "2000-06-06",
            "21:30",
            "男",
            2524,
            96,
            "source_reading_uncertain",
            "shun_only",
        ),
        (
            "2000-06-07",
            "15:30",
            "男",
            3322,
            96,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "2000-06-10",
            "21:30",
            "男",
            3328,
            97,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "2000-06-11",
            "07:30",
            "男",
            2510,
            89,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1994-06-01",
            "07:30",
            "女",
            3141,
            74,
            "source_printed_partial_blank",
            "both_directions",
        ),
        (
            "1994-06-01",
            "15:30",
            "男",
            2345,
            79,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1994-06-03",
            "17:30",
            "女",
            2248,
            80,
            "source_reading_uncertain",
            "neither_direction",
        ),
        (
            "1994-06-04",
            "05:30",
            "男",
            2743,
            77,
            "source_reading_uncertain",
            "both_directions",
        ),
        (
            "1994-06-05",
            "19:30",
            "男",
            3351,
            81,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "1988-06-02",
            "01:30",
            "男",
            2206,
            81,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1988-06-02",
            "03:30",
            "女",
            2307,
            81,
            "source_cell_visually_collated",
            "shun_only",
        ),
        (
            "1988-06-04",
            "11:30",
            "女",
            2513,
            84,
            "source_cell_visually_collated",
            "both_directions",
        ),
        (
            "1988-06-04",
            "17:30",
            "男",
            2816,
            84,
            "source_reading_uncertain",
            "both_directions",
        ),
        (
            "1988-06-04",
            "19:30",
            "男",
            2917,
            84,
            "source_reading_uncertain",
            "both_directions",
        ),
        (
            "1988-06-07",
            "09:30",
            "男",
            3315,
            86,
            "source_reading_uncertain",
            "both_directions",
        ),
        (
            "1988-06-10",
            "21:30",
            "男",
            2424,
            88,
            "source_reading_uncertain",
            "shun_only",
        ),
    ],
)
def test_canping_numbered_source_columns_and_missing_text_on_three_surfaces(
    date, time, gender, number, page, state, pair, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    fields = evidence_views(spec)["text_selection"]["fields"] + ["snapshot_text"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        verses = output["benming"]["verses"]
        selected = verses["selectionShun"]
        assert verses["numShun"] == selected["number"] == number
        assert selected["source_pdf_page"] == page and selected["cell_status"] == state
        assert selected["kind"] == ("male" if gender == "男" else "female")
        assert verses["pair_resolution"]["local_text_availability"] == pair
        wood_texts = {
            2206: "洞庭風葉舞，撫手上南山。",
            2307: "休彈陌上箏，莫娶桑間女。",
            2513: "風蒲美轉定，能化青蛇銅。",
            2816: "冰霜持令節，以候判陰陽。",
            2917: "江上一犁雨，芳菲起淡煙。",
            3315: "荏苒風霜至，竹梅花自開。",
            2424: "波中生日月，鏡底見乾坤。",
        }
        if number in wood_texts:
            assert verses["textShun"] == wood_texts[number]
            assert selected["element"] == "木"
            assert (
                output["numerology_evidence"]["canping_text_collation"][
                    "part_coverage"
                ]["木"]["collated_cells"]
                == 221
            )
            if number in {2816, 2917, 3315, 2424}:
                assert (
                    selected["number_attribution_status"] == "provisional_inherited_key"
                )
                assert selected["number_reading_uncertainties"]
                assert "editorial_unknown_marker" not in selected
                assert (
                    "编号遮损，暂按继承键定位，号文归属未定" in output["snapshot_text"]
                )
            if number == 2206:
                assert "editorial_unknown_marker" not in selected
                assert "reading_uncertainties" not in selected
                assert "number_attribution_status" not in selected
                assert (
                    selected["reading_revision"]["rereading_id"]
                    == "canping_wood_native_rereading_v1"
                )
                assert (
                    selected["reading_revision"]["previous_collation_version"]
                    == "1.8.0"
                )
                assert (
                    selected["reading_revision"]["previous_text"]
                    == "洞庭風葉舞，□手上南山。"
                )
        fire_texts = {
            3141: "孤舟流水急，○向溪灘○。",
            2345: "南柯鸞鳳立，天表景星行。",
            2248: "○○○○○，○○○○○。",
            2743: "巫山十二峰，不與凡人上。",
            3351: "彤弓架朱箭，用卵石麒麟。",
        }
        if number in fire_texts:
            assert verses["textShun"] == fire_texts[number]
            assert selected["element"] == "火"
            assert (
                output["numerology_evidence"]["canping_text_collation"][
                    "part_coverage"
                ]["火"]["collated_cells"]
                == 223
            )
            if number in {2248, 2743}:
                assert (
                    selected["number_attribution_status"] == "provisional_inherited_key"
                )
                assert selected["number_reading_uncertainties"]
                assert selected["reading_uncertainties"]
                assert "editorial_unknown_marker" not in selected
                assert (
                    "编号遮损，暂按继承键定位，号文归属未定" in output["snapshot_text"]
                )
        gold_texts = {
            2510: "梧桐金井上，枝葉接松筠。",
            3322: "圭田如玉潔，一點不生塵。",
            3328: "吾身何踐履，天外有煙霞。",
            2920: "青繩曾係足，何事○伐柯。",
            2524: "□作擎天柱，難當盛暑風。",
        }
        if number in gold_texts:
            assert verses["textShun"] == gold_texts[number]
            assert selected["element"] == "金"
            assert (
                output["numerology_evidence"]["canping_text_collation"][
                    "part_coverage"
                ]["金"]["collated_cells"]
                == 223
            )
            if number in {3322, 3328, 2524}:
                assert selected["inherited_text"] != verses["textShun"]
                assert "inherited_number" not in selected
                assert selected["reading_notes"]
            if number == 2524:
                assert selected["reading_uncertainties"]
                assert selected["editorial_unknown_marker"] == "□"
        if number == 3373:
            assert "天邊柳絮飛" in verses["textShun"]
            assert (
                verses["pair_resolution"]["same_number"]
                and verses["pair_resolution"]["distinct_numbers"] == 1
            )
        if number == 2335:
            assert verses["statusShun"] == "source_printed_blank"
            assert verses["selectionNi"]["cell_status"] == "row_absent_in_local_corpus"
        if number == 2332:
            assert verses["textShun"] == "南山秦嶺花，開向三冬雪。"
        if number == 2536:
            assert verses["textShun"] == "繡針為鐵杵，江海暗中瀛。"
        if number == 2344:
            assert verses["textShun"] == "春歸當斷○，梅子釀酸時。"
            assert verses["statusShun"] == "source_printed_partial_blank"
        if number == 2938:
            assert verses["textShun"] == "惟願日長好，□西還自東。"
            assert verses["statusShun"] == "source_reading_uncertain"
            assert selected["editorial_unknown_marker"] == "□"
            assert selected["reading_uncertainties"]
        if number in {2332, 2536, 2344, 2449}:
            counterpart = selected["witnesses"][0]
            expected = {
                2332: "商山秦嶺花，開向三冬雪。",
                2536: "繡針為鐵柱，江海暗中瀛。",
                2344: "春歸當斷路，梅子釀酸時。",
                2449: "月娥□桂子，圓缺又同情。",
            }
            assert counterpart["text"] == expected[number]
            assert counterpart["replaces_selected_text"] is False
            assert counterpart["relation"] == (
                "witness_reading_uncertain" if number == 2449 else "different_text"
            )
            assert (
                counterpart["body_pdf_page"]
                == {2332: 50, 2536: 52, 2344: 59, 2449: 60}[number]
            )
        if number in {2248, 2743, 2816, 2917, 3315, 2424}:
            assert selected["cell_status"] == "source_reading_uncertain"
            assert (
                selected["number_reading_evidence"]["resolution_status"] == "unresolved"
            )
            assert "□" in selected["number_reading_evidence"]["observed_header"]
            assert selected["body_reading_status"] == (
                "source_body_printed_blank"
                if number == 2248
                else "source_body_visually_read"
            )
            assert "原图编号仍未定，整格不计入已确定数" in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        assert evidence["selected_texts"][0]["verses"] == verses
        assert evidence["canping_text_collation"]["collated_cells"] == 1123
        assert evidence["canping_text_collation"]["unresolved_reading_cells"] == 47
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["selectionShun"] == selected
        assert trace["collation_sha256"] == evidence["canping_text_collation"]["sha256"]
        assert (
            trace["comparison_witness_sha256"]
            == evidence["canping_text_collation"]["comparison_witness"]["sha256"]
        )
        assert "[参评选条与来源]" in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,gender,half,xian,hou",
    [
        ("1990-06-12", "女", True, "乾為天", "天風姤"),
        ("1990-12-12", "男", False, "坤為地", "地雷復"),
    ],
)
def test_actual_yuantang_slots_and_half_year_provenance_on_three_surfaces(
    date, gender, half, xian, hou, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    assert "month_yang_ling" not in spec.request_model.model_fields
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": gender}
    fields = evidence_views(spec)["yuantang"]["fields"] + ["snapshot_text"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        chart = result["chart"]
        derivation = chart["yuantang_derivation"]
        assert chart["xian"]["name"] == xian and chart["xian"]["yuan"] == 4
        assert chart["hou"]["name"] == hou and chart["hou"]["yuan"] == 1
        assert chart["yangLing"] is half
        assert derivation["half_year"]["value"] is half
        assert derivation["half_year"]["basis"] == "solstice_instant"
        assert derivation["half_year"]["birth_instant_utc"].endswith("+00:00")
        assert derivation["half_year"]["candidate_values"] == [half]
        assert derivation["half_year"]["counterfactuals"][int(half)]["xian_yuan"] == 4
        assert derivation["placement"]["slot_positions"] == [6, 5, 4, 6, 5, 4]
        assert derivation["placement"]["hour_index"] == 6
        trace = next(
            t["facts"]
            for t in result["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == derivation["ruleset_id"]
        )
        assert trace == derivation
        assert "半年反事实比较（非两个实际出生时刻）" in result["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,phase,gua,line,pages,excerpt",
    [
        ("2000-03-08", "09:33:00", 1, "乾為天", 6, [121], "高而無名"),
        ("1960-02-15", "01:30:00", 0, "坤為地", 2, [122], "力量大"),
    ],
)
def test_source_commentary_and_unselected_branches_on_three_surfaces(
    date, time, phase, gua, line, pages, excerpt, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": time}
    fields = evidence_views(spec)["selected_texts"]["fields"] + ["snapshot_text"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        evidence = output["numerology_evidence"]
        selected = evidence["selected_texts"][phase]
        assert (selected["hexagram"], selected["line"]) == (gua, line)
        text = selected["text"]
        assert excerpt in text["detail"] and text["detail"] in output["snapshot_text"]
        assert text["text_provenance"]["commentary_pdf_pages"] == pages
        assert text["text_provenance"]["poem_presence_in_reviewed_sections"] is False
        assert text["commentary_branch_selection"]["selected_section_ids"] == []
        assert all(s["applicability"] is None for s in text["commentary_sections"])
        assert (
            evidence["commentary_collation"]["pending_line_commentaries"]
            == PENDING_COUNT
        )
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "heluo_selected_line_collation_v1"
        )
        assert trace["commentary_sha256"] == evidence["commentary_collation"]["sha256"]
        assert trace["selections"][phase]["commentary_pdf_pages"] == pages


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize("flag", ["__omitted__", True])
def test_default_or_explicit_solar_time_without_longitude_is_rejected(
    key, flag, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**INPUT}
    if flag == "__omitted__":
        payload.pop("use_true_solar_time")
    else:
        payload["use_true_solar_time"] = flag
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "options,longitude,source,used",
    [
        ({"use_true_solar_time": False}, None, None, False),
        ({"use_true_solar_time": True, "lon": "75"}, 75, "lon", True),
        ({"use_true_solar_time": True, "gps_lon": 0}, 0, "gps_lon", True),
    ],
)
def test_known_birth_clock_and_longitude_source_on_three_surfaces(
    key, options, longitude, source, used, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**INPUT, **options}
    fields = [
        "analysis_context",
        "four_pillars",
        "numerology_evidence.birth_clock",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        clock = output["numerology_evidence"]["birth_clock"]
        assert (
            clock["longitude"] == output["analysis_context"]["longitude"] == longitude
        )
        assert clock["longitude_source"] == source and clock["longitude_used"] is used
        assert (
            next(
                t["facts"]
                for t in output["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == clock["policy_id"]
            )
            == clock
        )
        assert "[出生钟时与经度]" in output["snapshot_text"]


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_published_birth_clock_view_works_in_real_mcp(key):
    spec = SPECS[key]
    result = asyncio.run(
        native(
            spec,
            {
                **INPUT,
                "fields": evidence_views(spec)["birth_clock"]["fields"],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
    )
    assert not result.is_error and "snapshot_text" not in result.structured_content
    assert (
        result.structured_content["numerology_evidence"]["birth_clock"]["longitude"]
        is None
    )


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "clock", ["__omitted__", None, "", " ", "未知", "09:33:00Z", "24:00"]
)
def test_numerology_unknown_clock_is_rejected_on_three_surfaces(
    key, clock, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**INPUT, "time": clock}
    if clock == "__omitted__":
        payload.pop("time")
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


@pytest.mark.parametrize(
    "date,gua,page,phase_index,matched",
    [
        ("2026-11-12", "震為雷", 240, 1, True),
        ("2026-12-09", "水澤節", 263, 1, True),
        ("2000-09-20", "乾為天", 119, 0, False),
    ],
)
def test_corrected_assigned_month_and_same_run_trace_on_three_surfaces(
    date, gua, page, phase_index, matched, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": "男"}
    fields = ["judge.deTime", "judge.month_affinity", "numerology_evidence.rule_trace"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        evidence = output["judge"]["month_affinity"]
        assert output["judge"]["deTime"] is matched
        row = evidence["phases"][phase_index]
        assert row["gua"] == gua and row["source_pdf_page"] == page
        assert row["assigned_month_match"] is matched
        if gua == "乾為天":
            assert evidence["birth_month_number"] == 8
            assert row["additional_windows"][0]["match"] is None
            assert row["additional_windows"][0]["last_month_inclusive"] is None
        trace = next(
            t
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == evidence["ruleset_id"]
        )
        assert trace["facts"] == evidence


def test_published_month_affinity_view_can_be_used_in_a_real_mcp_call():
    spec = SPECS["heluo"]
    view = evidence_views(spec)["month_affinity"]
    result = asyncio.run(
        native(
            spec,
            {
                **INPUT,
                "date": "2026-12-09",
                "time": "09:33:00",
                "gender": "男",
                "fields": view["fields"],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
    )
    assert not result.is_error
    assert (
        result.structured_content["judge"]["month_affinity"]["phases"][1][
            "source_pdf_page"
        ]
        == 263
    )
    assert "snapshot_text" not in result.structured_content


def test_published_body_relations_view_on_three_surfaces(rest, tmp_path, capsys):
    spec = SPECS["heluo"]
    outputs = projected_outputs(
        spec,
        {**INPUT, "date": "1975-02-18", "time": "09:33:00", "gender": "男"},
        evidence_views(spec)["body_relations"]["fields"],
        rest,
        tmp_path,
        capsys,
        include_snapshot_text=False,
    )
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        body = output["judge"]["deTi"]
        assert (
            body["present"] is None and body["generating_qi"]["condition_match"] is True
        )
        assert "snapshot_text" not in output


@pytest.mark.parametrize(
    "date,fh,hg_change,fh_change",
    [
        ("2000-05-15", ["離", "巽"], "lost", "retained"),
        ("2026-04-10", ["離", "巽"], "gained", "lost"),
        ("2026-12-23", ["離"], "absent", "absent"),
    ],
)
def test_phase_qi_and_overlapping_fanhua_agree_on_three_surfaces(
    date, fh, hg_change, fh_change, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": "男"}
    fields = [
        "judge.qi_phases",
        "judge.fanhua",
        "solar_term",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        qi = output["judge"]["qi_phases"]
        assert output["solar_term"]["fh"] == output["judge"]["fanhua"]["guas"] == fh
        assert (
            qi["candidate_basis"] == "birth_instant"
            and qi["complete_assessment"] is False
        )
        assert qi["birth_instant_utc"] == output["solar_term"]["anchor_utc"]
        changes = {t["kind"]: t["change"] for t in qi["transitions"]}
        assert (changes["huagong"], changes["fanhua"]) == (hg_change, fh_change)
        assert [row["phase"] for row in qi["phases"]] == ["xian", "hou"]
        trace = next(
            t
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == qi["ruleset_id"]
        )
        assert trace["facts"] == qi
        assert "[先后天·元气化工分列]" in output["snapshot_text"]


def test_published_qi_phases_view_works_in_real_mcp():
    spec = SPECS["heluo"]
    result = asyncio.run(
        native(
            spec,
            {
                **INPUT,
                "date": "2000-05-15",
                "gender": "男",
                "fields": evidence_views(spec)["qi_phases"]["fields"],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
    )
    assert not result.is_error and "snapshot_text" not in result.structured_content
    assert len(result.structured_content["judge"]["qi_phases"]["phases"]) == 2


@pytest.mark.parametrize(
    "date,year,absence,condition",
    [
        ("1975-02-18", "乙卯", True, True),
        ("2000-05-15", "庚辰", False, False),
        ("1986-02-10", "丙寅", True, False),
        ("2001-01-24", "庚辰", False, False),
    ],
)
def test_nayin_direction_qualifier_and_unresolved_deti_on_three_surfaces(
    date, year, absence, condition, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": "男"}
    fields = [
        "judge.deTi",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        actual = output["judge"]["deTi"]
        assert actual["year_ganzhi"] == year and actual["yuanqi_absent"] is absence
        assert actual["generating_qi"]["condition_match"] is condition
        assert actual["present"] is None and actual["complete_assessment"] is False
        assert len(actual["bodies"]) == 8
        trace = next(
            t
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == actual["ruleset_id"]
        )
        assert trace["facts"] == actual
        assert f"年柱{year}，纳音{actual['nayin']}" in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,phase_index,gua,month,assigned_match,window_matches,opposed",
    [
        ("2000-03-20", 1, "水風井", 2, True, [None], False),
        ("2000-04-19", 0, "水風井", 3, False, [None], False),
        ("2000-02-10", 0, "澤雷隨", 1, False, [True, True], True),
        ("2000-06-22", 0, "雷地豫", 5, True, [False], False),
        ("2002-10-19", 1, "山雷頤", 9, False, [False, None], False),
        ("2001-01-24", 1, "雷水解", 12, True, [None, None], False),
    ],
)
def test_discrete_conflicting_and_qualified_month_conditions_on_three_surfaces(
    date,
    phase_index,
    gua,
    month,
    assigned_match,
    window_matches,
    opposed,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "09:33:00", "gender": "男"}
    fields = ["judge.month_affinity", "numerology_evidence.rule_trace"]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        evidence = output["judge"]["month_affinity"]
        assert evidence["birth_month_number"] == month
        assert (
            evidence["reviewed_hexagram_introductions"],
            evidence["explicit_assigned_months"],
            evidence["additional_month_clauses"],
        ) == (64, 63, 21)
        row = evidence["phases"][phase_index]
        assert row["gua"] == gua and row["assigned_month_match"] is assigned_match
        assert row["opposed_month_conditions"] is opposed
        assert [w["match"] for w in row["additional_windows"]] == window_matches
        if date in {"2000-03-20", "2001-01-24"}:
            # These previously returned false for the whole qualified phrase.
            # Preserve the definite false month label and the unresolved scope.
            window = row["additional_windows"][0]
            assert window["month_label_match"] is False
            assert window["qualifiers"]
            assert window["status"] == "additional_condition_unresolved"
            assert window["match"] is None
        trace = next(
            t
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == evidence["ruleset_id"]
        )
        assert trace["facts"] == evidence


def test_heluo_collation_and_normalized_gender_agree_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": "2000-06-15", "time": "09:33:00", "gender": "FEMALE"}
    fields = [
        "chart.gender",
        "numerology_evidence.selected_texts",
        "numerology_evidence.yaoci_collation",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["chart"]["gender"] == "女"
        evidence = output["numerology_evidence"]
        assert evidence["yaoci_collation"]["pending_line_headers"] == PENDING_COUNT
        xian, hou = evidence["selected_texts"]
        assert xian["hexagram"] == "天水訟" and xian["line"] == 3
        assert xian["text"]["text_provenance"]["pdf_page"] == 132
        assert hou["text"]["yaoci"] == "既雨既處，尚德載，婦貞厲，月幾望，君子征凶。"
        assert hou["text"]["text_provenance"]["pdf_page"] == 141


@pytest.mark.parametrize("gender", ["__omitted__", None, "", "未知", "typo"])
def test_heluo_missing_or_unknown_gender_is_rejected_on_three_surfaces(
    gender, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "gender": gender}
    if gender == "__omitted__":
        payload.pop("gender")
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_numerology_facts_and_provenance_agree_on_three_surfaces(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    response = rest.post(
        spec.rest_path, json=INPUT, params={"as_of": "2026-10-12T02:00:00Z"}
    )
    code, local = call_cli(
        spec, INPUT, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, INPUT))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert (
            output["numerology_evidence"]["validation_status"]["prediction"]
            == "not_validated"
        )
        assert output["run_metadata"]["provenance"]["ruleset"]
        if key == "heluo":
            assert output["solar_term"]["term"] == "夏至"
            assert output["chart"]["yangLing"] is False
            assert output["chart"]["yangLingBasis"] == "solstice_instant"
            trace = next(
                row
                for row in output["numerology_evidence"]["rule_trace"]
                if row["rule_id"] == "yuantang_and_houtian"
            )
            assert trace["facts"]["yang_ling_basis"] == "solstice_instant"
            assert (
                trace["facts"]["birth_instant_utc"]
                == output["solar_term"]["anchor_utc"]
            )
        else:
            assert output["input_normalized"]["method"] == "gu"


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_numerology_evidence_supports_strict_projection(key, rest, tmp_path, capsys):
    spec = SPECS[key]
    fields = [
        "numerology_evidence.rulesets",
        "numerology_evidence.validation_status",
        "numerology_evidence.rule_trace",
    ]
    options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response = rest.post(
        spec.rest_path,
        json=INPUT,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        INPUT,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, INPUT, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert set(output["numerology_evidence"]) == {
            "rulesets",
            "validation_status",
            "rule_trace",
        }
        assert "snapshot_text" not in output


def test_invalid_canping_method_fails_on_all_surfaces(rest, tmp_path, capsys):
    spec = SPECS["canping"]
    payload = {**INPUT, "method": "typo"}
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_published_first_view_is_sufficient_for_an_actual_mcp_calculation(key):
    spec = SPECS[key]
    protocol = asyncio.run(
        native(
            spec,
            example_input(spec),
            fields=suggested_fields(spec),
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert not protocol.is_error
    output = protocol.structured_content
    assert output["numerology_evidence"]["rule_trace"]
    assert output["numerology_evidence"]["selected_texts"]
    assert output["numerology_evidence"]["rulesets"]
    assert output["numerology_evidence"]["unresolved_rules"]
    assert "snapshot_text" not in output and "liunian_series" not in output


def test_published_number_conditions_view_delivers_full_literal_conditions():
    spec = SPECS["heluo"]
    view = evidence_views(spec)["number_conditions"]
    protocol = asyncio.run(
        native(
            spec,
            example_input(spec),
            fields=view["fields"],
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=0,
        )
    )
    assert not protocol.is_error
    output = protocol.structured_content
    evidence = output["judge"]["seasonal_numbers"]
    assert len(evidence["numerical_conditions"]) == 11
    assert len(evidence["seasonal_windows"]) == 6
    assert evidence["numbers"]["tian"]["value"] == output["chart"]["tian"]
    assert evidence["numbers"]["di"]["value"] == output["chart"]["di"]
    assert any(
        r["ruleset_id"] == evidence["ruleset_id"]
        for r in output["numerology_evidence"]["rulesets"]
    )


def test_heluo_annual_month_and_day_selection_agrees_on_all_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "analysis_year": 2027, "month_index": 3, "day_index": 10}
    fields = [
        "heluo_timing.ruleset_id",
        "heluo_timing.calendar_policy",
        "heluo_timing.selected_annual",
        "heluo_timing.selected_month",
        "heluo_timing.selected_day",
        "heluo_timing.selected_texts",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        timing = output["heluo_timing"]
        assert timing["selected_annual"]["year_label"] == 2027
        assert timing["selected_month"]["month_index"] == 3
        assert timing["selected_day"]["day_index"] == 10
        assert len(timing["selected_texts"]) == 3
        assert "annual_rows" not in timing
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)


@pytest.mark.parametrize(
    "change",
    [
        {"month_index": 1},
        {"analysis_year": 2027, "day_index": 1},
        {"analysis_year": True},
        {"analysis_year": 2027, "month_index": 2, "day_index": 31},
    ],
)
def test_invalid_heluo_sequence_selection_fails_on_all_surfaces(
    change, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, **change}
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


def test_heluo_timing_never_uses_the_current_year_implicitly(rest):
    outputs = []
    for as_of in ["2027-01-01T00:00:00Z", "2032-01-01T00:00:00Z"]:
        r = rest.post(
            SPECS["heluo"].rest_path,
            json=INPUT,
            params={"as_of": as_of, "response_char_limit": 0},
        )
        assert r.status_code == 200
        output = r.json()
        assert output["heluo_timing"]["selected_annual"] is None
        assert output["run_metadata"]["determinism"]["uses_current_time"] is False
        outputs.append(business(output))
    assert outputs[0] == outputs[1]


def test_claim_verification_does_not_substitute_a_natal_position_for_an_annual_position(
    rest,
):
    r = rest.post(
        SPECS["heluo"].rest_path,
        json={**INPUT, "analysis_year": 2027},
        params={"response_char_limit": 0},
    )
    assert r.status_code == 200
    output = r.json()
    annual = output["heluo_timing"]["selected_annual"]["pos"]
    natal = output["chart"]["xian"]["yuan"]
    assert annual != natal
    receipt = output["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="heluo_timing.selected_annual.pos",
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    assert (
        verify_calculation_claims(output, [claim(annual)])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(output, [claim(natal)])["status"] == "rejected"


def test_heluo_real_cli_flags_parse_strict_integer_selectors(capsys):
    code = cli_run(
        [
            "heluo",
            "--date",
            "1990-06-15",
            "--time",
            "09:33:00",
            "--zone",
            "Asia/Shanghai",
            "--gender",
            "男",
            "--use-true-solar-time",
            "false",
            "--analysis-year",
            "2028",
            "--month-index",
            "3",
            "--day-index",
            "10",
            "--fields",
            "heluo_timing.selected_day",
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ]
    )
    import json

    output = json.loads(capsys.readouterr().out)
    assert code == 0 and output["heluo_timing"]["selected_day"]["day_index"] == 10


def test_corrected_najia_and_positional_evidence_agree_across_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": "2000-05-15", "time": "09:33:00", "gender": "男"}
    fields = [
        "judge.deSheng",
        "judge.deSheng_policy",
        "judge.najia",
        "numerology_evidence.rule_trace",
    ]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["judge"]["deSheng"] is False
        assert all(
            len(p["lines"]) == 6 and not p["matches"] for p in output["judge"]["najia"]
        )
        trace = next(
            t
            for t in output["numerology_evidence"]["rule_trace"]
            if t["rule_id"] == "year_najia_at_actual_line_positions"
        )
        assert trace["facts"]["phases"] == output["judge"]["najia"]
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)


@pytest.mark.parametrize(
    "profile,status",
    [("bazi_appendix_v1", "not_started"), ("bazi_continuous_v1", "active")],
)
def test_canping_query_profiles_preserve_their_real_selected_segment_across_surfaces(
    profile, status, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {
        **INPUT,
        "date": "2026-02-06",
        "time": "04:02:00",
        "gender": "女",
        "dayun_method": profile,
        "analysis_datetime": "2027-02-05T12:00:00+08:00",
    }
    fields = [
        "canping_timing",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rulesets",
    ]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        timing = output["canping_timing"]
        assert (
            timing["profile_id"] == profile and timing["selected"]["status"] == status
        )
        if status == "not_started":
            assert "numShun" not in timing["selected"]
            assert len(output["numerology_evidence"]["selected_texts"]) == 1
        else:
            assert (
                output["numerology_evidence"]["selected_texts"][-1]["verses"]
                == timing["selected"]["verses"]
            )
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)


@pytest.mark.parametrize(
    "change",
    [
        {"gender": None},
        {"gender": "未知"},
        {"analysis_datetime": "2027-01-01T00:00:00"},
        {
            "dayun_method": "legacy_minggong_v1",
            "analysis_datetime": "2027-01-01T00:00:00Z",
        },
        {"dayun_method": "typo"},
    ],
)
def test_canping_missing_or_conflicting_clock_and_direction_inputs_fail_consistently(
    change, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, **change}
    http = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 422 and code != 0 and protocol.is_error


def test_canping_real_cli_flags_select_an_actual_dayun_without_implicit_current_time(
    capsys,
):
    import json

    code = cli_run(
        [
            "canping",
            "--date",
            "2026-02-06",
            "--time",
            "04:02:00",
            "--zone",
            "Asia/Shanghai",
            "--gender",
            "女",
            "--use-true-solar-time",
            "false",
            "--dayun-method",
            "bazi_appendix_v1",
            "--analysis-datetime",
            "2037-02-06T04:02:00+08:00",
            "--fields",
            "canping_timing.selected",
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["canping_timing"]["selected"]["dayun_pillar"] == "戊子"
    assert result["canping_timing"]["selected"]["numShun"] == 2835
    assert result["run_metadata"]["determinism"]["uses_current_time"] is False


@pytest.mark.parametrize(
    "date, expected",
    [
        ("2026-02-10", {"yang_insufficient", "yang_middle"}),
        ("2026-08-15", {"yin_insufficient", "yin_middle"}),
        ("2026-03-25", set()),
    ],
)
def test_seasonal_number_conditions_keep_real_windows_and_evidence_on_three_surfaces(
    date, expected, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**INPUT, "date": date, "time": "12:00:00"}
    fields = ["judge.seasonal_numbers", "numerology_evidence.rule_trace"]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        evidence = output["judge"]["seasonal_numbers"]
        assert {
            w["rule_id"] for w in evidence["seasonal_windows"] if w["active"]
        } == expected
        assert not evidence["complete_assessment"]
        trace = next(
            r
            for r in output["numerology_evidence"]["rule_trace"]
            if r["rule_id"] == evidence["ruleset_id"]
        )
        assert trace["facts"] == evidence


@pytest.mark.parametrize(
    "at,number,text,state",
    [
        (
            "2017-06-01T12:00:00+08:00",
            2743,
            "意欲搆舟子，得乘□。",
            "source_reading_uncertain",
        ),
        (
            "2056-06-01T12:00:00+08:00",
            3242,
            "良馬羈其足，百鞭亦難進。",
            "source_cell_visually_collated",
        ),
        (
            "2060-06-01T12:00:00+08:00",
            2846,
            "風雲三吐哺，盡禮詩○賢。",
            "source_printed_partial_blank",
        ),
        (
            "2066-06-01T12:00:00+08:00",
            3351,
            "花間逢○○，多不減芸香。",
            "source_printed_partial_blank",
        ),
    ],
)
def test_fire_actual_query_keeps_lower_column_circles_and_number_uncertainty_across_surfaces(
    at, number, text, state, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": "1994-06-01", "time": "07:30", "analysis_datetime": at}
    fields = [
        "canping_timing.selected",
        "numerology_evidence.selected_texts",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        selected = output["canping_timing"]["selected"]
        verses = selected["verses"]
        provenance = verses["selectionShun"]
        assert (
            selected["numShun"] == verses["numShun"] == provenance["number"] == number
        )
        assert verses["textShun"] == text and provenance["cell_status"] == state
        assert (
            provenance["kind"] == "luck" and provenance["column"] == "lower_shared_luck"
        )
        assert output["numerology_evidence"]["selected_texts"][-1]["verses"] == verses
        assert text in output["snapshot_text"]
        if number == 2743:
            assert (
                provenance["number_attribution_status"] == "provisional_inherited_key"
            )
            assert provenance["number_reading_uncertainties"]
            assert provenance["editorial_unknown_marker"] == "□"
            assert "编号遮损，暂按继承键定位，号文归属未定" in output["snapshot_text"]


@pytest.mark.parametrize(
    "at,number,text,state",
    [
        (
            "2002-07-01T12:00:00+08:00",
            3115,
            "登高○○○，傳命探梅花。",
            "source_printed_partial_blank",
        ),
        (
            "2021-07-01T12:00:00+08:00",
            2208,
            "藍橋玉壺○，鴛鴦解鳴雨。",
            "source_printed_partial_blank",
        ),
        (
            "2041-07-01T12:00:00+08:00",
            2414,
            "準定用權衡，輕重當自取。",
            "source_cell_visually_collated",
        ),
        (
            "2052-07-01T12:00:00+08:00",
            2424,
            "杏花雨濛濛，喜蘇人○犁。",
            "source_reading_uncertain",
        ),
    ],
)
def test_wood_actual_query_keeps_lower_column_circles_and_provisional_header_across_surfaces(
    at, number, text, state, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": "1988-06-02", "time": "03:30", "analysis_datetime": at}
    fields = [
        "canping_timing.selected",
        "numerology_evidence.selected_texts",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        selected = output["canping_timing"]["selected"]
        verses = selected["verses"]
        provenance = verses["selectionShun"]
        assert (
            selected["numShun"] == verses["numShun"] == provenance["number"] == number
        )
        assert verses["textShun"] == text and provenance["cell_status"] == state
        assert (
            provenance["kind"] == "luck" and provenance["column"] == "lower_shared_luck"
        )
        assert output["numerology_evidence"]["selected_texts"][-1]["verses"] == verses
        assert text in output["snapshot_text"]
        if number == 2424:
            assert (
                provenance["number_attribution_status"] == "provisional_inherited_key"
            )
            assert provenance["number_reading_uncertainties"]
            assert "editorial_unknown_marker" not in provenance
            assert "编号遮损，暂按继承键定位，号文归属未定" in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,gender,at,number,text,state",
    [
        (
            "1990-06-04",
            "05:30",
            "男",
            None,
            2460,
            "沈李浮瓜景，廣寒宮似水。",
            "source_cell_visually_collated",
        ),
        (
            "1990-06-01",
            "09:30",
            "女",
            None,
            2971,
            "○○有佳人，青鏡朱顏改。",
            "source_printed_partial_blank",
        ),
        (
            "1990-06-02",
            "19:30",
            "女",
            None,
            3377,
            "晝夕掩重門，虛空久寂寞。",
            "source_cell_visually_collated",
        ),
        (
            "1990-06-06",
            "13:30",
            "女",
            None,
            2666,
            "汀蘭井岸芷，泛○奉浮家。",
            "source_printed_partial_blank",
        ),
        (
            "1990-06-01",
            "17:30",
            "男",
            None,
            3375,
            "東山煙霞佈，木棹入扁舟。",
            "source_cell_visually_collated",
        ),
        (
            "1990-06-02",
            "03:30",
            "女",
            "2087-08-05T14:08:07.254006+08:00",
            2272,
            "明珠生蚌內，方寸自然光。",
            "source_cell_visually_collated",
        ),
        (
            "1990-06-02",
            "03:30",
            "女",
            "2011-08-06T03:27:40.256321+08:00",
            3363,
            "魚龍在釣□，志樂在其中。",
            "source_reading_uncertain",
        ),
        (
            "1990-06-02",
            "03:30",
            "女",
            "2066-08-05T11:43:59.323403+08:00",
            3377,
            "固壘○○處，隄防有不虞。",
            "source_printed_partial_blank",
        ),
    ],
)
def test_earth_readings_and_review_completion_across_surfaces(
    date, time, gender, at, number, text, state, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    if at is not None:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "numerology_evidence.interpretation_constraints",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        verses = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = verses["selectionShun"]
        assert verses["numShun"] == selected["number"] == number
        assert verses["textShun"] == text and selected["cell_status"] == state
        assert selected["element"] == "土"
        assert selected["kind"] == (
            "luck" if at else "male" if gender == "男" else "female"
        )
        assert selected["column"] == (
            "lower_shared_luck"
            if at
            else "upper_male" if gender == "男" else "middle_female"
        )
        assert "number_attribution_status" not in selected
        if number == 3377 and selected["kind"] == "female":
            assert (
                selected["reading_revision"]["previous_text"]
                == "□夕掩重門，虛空久寂寞。"
            )
            assert (
                selected["reading_revision"]["previous_cell_status"]
                == "source_reading_uncertain"
            )
            assert (
                selected["reading_revision"]["rereading_id"]
                == "canping_earth_native_rereading_v1"
            )
        if "□" in text:
            assert (
                selected["reading_uncertainties"]
                and selected["editorial_unknown_marker"] == "□"
            )
        else:
            assert "editorial_unknown_marker" not in selected
        evidence = output["numerology_evidence"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == verses
        summary = evidence["canping_text_collation"]
        assert summary["collated_cells"] == 1123
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["numbered_table_visual_review_complete"] is True
        assert summary["numbered_table_clear_readings_complete"] is False
        assert "independent_second_review_pending" in summary["review_status"]
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]
        assert any(
            "目读覆盖完成不等于疑读消除" in c
            for c in evidence["interpretation_constraints"]
        )
        assert text in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,gender,at,number,text,state",
    [
        (
            "1996-06-02",
            "09:30",
            "女",
            None,
            3241,
            "江天欲暮時，惆悵神仙侶。",
            "source_cell_visually_collated",
        ),
        (
            "1996-06-04",
            "00:30",
            "男",
            None,
            2538,
            "坐井觀天象，明知八陣圖。",
            "source_cell_visually_collated",
        ),
        (
            "1996-06-01",
            "15:30",
            "女",
            None,
            2443,
            "□女乘龍去，猶疑結子。",
            "source_reading_uncertain",
        ),
        (
            "1996-06-04",
            "19:30",
            "女",
            None,
            2348,
            "晚風雷芍藥，須避巽風臺。",
            "source_cell_visually_collated",
        ),
        (
            "1996-06-06",
            "09:30",
            "女",
            None,
            2845,
            "嫣婉○宜求，難教霜點鬢。",
            "source_printed_partial_blank",
        ),
        (
            "1996-06-02",
            "09:30",
            "女",
            "2098-08-05T06:21:09.187832+08:00",
            2243,
            "□升被雲大，時下暗光輝。",
            "source_reading_uncertain",
        ),
        (
            "1996-06-02",
            "09:30",
            "女",
            "2086-08-05T08:22:13.528756+08:00",
            2344,
            "下和獻璞玉，先辱後榮恩。",
            "source_cell_visually_collated",
        ),
        (
            "1996-06-02",
            "09:30",
            "女",
            "2042-08-05T16:05:52.036567+08:00",
            2441,
            "寒花紅日近，迤運有疏通。",
            "source_cell_visually_collated",
        ),
        (
            "1996-06-02",
            "09:30",
            "女",
            "2015-04-04T10:44:14.160290+08:00",
            3041,
            "畫舫過洪波，棹○難得太。",
            "source_printed_partial_blank",
        ),
    ],
)
def test_native_water_rereadings_keep_prior_uncertainty_across_surfaces(
    date, time, gender, at, number, text, state, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    if at is not None:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "numerology_evidence.interpretation_constraints",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        verses = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = verses["selectionShun"]
        assert verses["numShun"] == selected["number"] == number
        assert verses["textShun"] == text and selected["cell_status"] == state
        assert selected["element"] == "水"
        assert selected["kind"] == (
            "luck" if at else "male" if gender == "男" else "female"
        )
        assert selected["column"] == (
            "lower_shared_luck"
            if at
            else "upper_male" if gender == "男" else "middle_female"
        )
        assert "number_attribution_status" not in selected
        if "□" in text:
            assert (
                selected["reading_uncertainties"]
                and selected["editorial_unknown_marker"] == "□"
            )
        else:
            assert "editorial_unknown_marker" not in selected
        revision = selected["reading_revision"]
        assert revision["rereading_id"] == "canping_water_native_rereading_v1"
        assert revision["previous_cell_status"] == "source_reading_uncertain"
        assert "□" in revision["previous_text"]
        assert "同馆藏原图复读，旧疑读另存" in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == verses
        summary = evidence["canping_text_collation"]
        assert summary["collated_cells"] == 1123
        witness = summary["rereading_witness"]
        assert (
            witness["resolved_cells"] == 30 and witness["still_uncertain_cells"] == 10
        )
        assert (
            witness["new_numbered_cells_examined"]
            == witness["new_independent_reviews"]
            == 0
        )
        assert len(witness["pages"]) == 7
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["numbered_table_visual_review_complete"] is True
        assert summary["numbered_table_clear_readings_complete"] is False
        assert "independent_second_review_pending" in summary["review_status"]
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]
        assert any(
            "目读覆盖完成不等于疑读消除" in c
            for c in evidence["interpretation_constraints"]
        )
        assert text in output["snapshot_text"]


@pytest.mark.parametrize(
    "date,time,gender,at,number",
    [
        ("1994-06-02", "19:30", "女", None, 2448),
        ("1994-06-02", "13:30", "女", None, 3345),
        ("1994-06-02", "19:30", "女", "2108-08-05T16:33:12.299084+08:00", 2341),
        ("1994-06-02", "19:30", "女", "2075-08-05T16:26:12.779734+08:00", 2347),
        ("1994-06-02", "19:30", "女", "2064-08-05T00:09:50.508552+08:00", 2349),
        ("1994-06-02", "19:30", "女", "2030-08-05T18:03:23.238313+08:00", 2543),
        ("1994-06-02", "19:30", "女", "2099-08-05T12:06:49.602995+08:00", 3345),
        ("1994-06-02", "19:30", "男", "2038-08-05T16:58:22.971398+08:00", 2547),
    ],
)
def test_native_fire_rereadings_keep_separate_witnesses_across_surfaces(
    date, time, gender, at, number, rest, tmp_path, capsys
):
    import json
    from pathlib import Path

    reference = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/canping_fire_rereading_v1/reference.json"
        ).read_text()
    )
    kind = "luck" if at else "female"
    expected = next(
        c for c in reference["cells"] if (c["number"], c["kind"]) == (number, kind)
    )
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    if at:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        v = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = v["selectionShun"]
        assert v["numShun"] == selected["number"] == number
        assert (
            v["textShun"] == expected["text"]
            and selected["cell_status"] == expected["state"]
        )
        assert selected["element"] == "火" and selected["kind"] == kind
        assert selected["source_pdf_page"] == expected["pdf_page"]
        assert "number_attribution_status" not in selected
        revision = selected["reading_revision"]
        assert revision["rereading_id"] == reference["fixture_id"]
        assert revision["previous_collation_version"] == "1.7.0"
        assert revision["previous_text"] == expected["previous_text"]
        assert revision["previous_cell_status"] == "source_reading_uncertain"
        assert ("editorial_unknown_marker" in selected) == ("□" in expected["text"])
        assert "同馆藏原图复读，旧疑读另存" in output["snapshot_text"]
        assert expected["text"] in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        summary = evidence["canping_text_collation"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == v
        assert summary["version"] == "1.11.0" and summary["collated_cells"] == 1123
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["rereading_witness"]["resolved_cells"] == 30
        witness = summary["additional_rereading_witnesses"][0]
        assert witness["fixture_id"] == reference["fixture_id"]
        assert witness["resolved_cells"] == 6 and witness["still_uncertain_cells"] == 5
        assert (
            witness["new_numbered_cells_examined"]
            == witness["new_independent_reviews"]
            == 0
        )
        assert (
            witness["native_region_count"] == 24 and witness["reused_region_count"] == 8
        )
        assert len(witness["pages"]) == 6
        assert summary["number_reading_witness"]["headers_still_uncertain"] == 6
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]


@pytest.mark.parametrize(
    "date,time,gender,at,number",
    [
        ("1988-06-04", "09:30", "男", None, 2412),
        ("1988-06-05", "19:30", "女", None, 2818),
        ("1988-06-04", "09:30", "男", "2025-08-05T13:06:18.009631+08:00", 2519),
    ],
)
def test_native_wood_rereadings_keep_all_three_batches_across_surfaces(
    date, time, gender, at, number, rest, tmp_path, capsys
):
    import json
    from pathlib import Path

    reference = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/canping_wood_rereading_v1/reference.json"
        ).read_text()
    )
    kind = "luck" if at else "male" if gender == "男" else "female"
    expected = next(
        c for c in reference["cells"] if (c["number"], c["kind"]) == (number, kind)
    )
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    if at:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        v = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = v["selectionShun"]
        assert v["numShun"] == selected["number"] == number
        assert (
            v["textShun"] == expected["text"]
            and selected["cell_status"] == expected["state"]
        )
        assert selected["element"] == "木" and selected["kind"] == kind
        assert selected["source_pdf_page"] == expected["pdf_page"]
        assert selected["column"] == (
            "lower_shared_luck"
            if at
            else "upper_male" if gender == "男" else "middle_female"
        )
        assert "number_attribution_status" not in selected
        revision = selected["reading_revision"]
        assert revision["rereading_id"] == reference["fixture_id"]
        assert revision["previous_collation_version"] == "1.8.0"
        assert revision["previous_text"] == expected["previous_text"]
        assert revision["previous_cell_status"] == "source_reading_uncertain"
        assert ("editorial_unknown_marker" in selected) == ("□" in expected["text"])
        assert "同馆藏原图复读，旧疑读另存" in output["snapshot_text"]
        assert expected["text"] in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        summary = evidence["canping_text_collation"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == v
        assert summary["version"] == "1.11.0" and summary["collated_cells"] == 1123
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["rereading_witness"]["resolved_cells"] == 30
        assert (
            summary["additional_rereading_witnesses"][0]["fixture_id"]
            == "canping_fire_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][0]["resolved_cells"] == 6
        witness = next(
            w
            for w in summary["additional_rereading_witnesses"]
            if w["fixture_id"] == reference["fixture_id"]
        )
        assert witness["fixture_id"] == reference["fixture_id"]
        assert witness["resolved_cells"] == 3 and witness["still_uncertain_cells"] == 1
        assert (
            witness["new_numbered_cells_examined"]
            == witness["new_independent_reviews"]
            == 0
        )
        assert (
            witness["native_region_count"] == 16 and witness["reused_region_count"] == 8
        )
        assert len(witness["pages"]) == 4
        assert summary["number_reading_witness"]["headers_still_uncertain"] == 6
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]


@pytest.mark.parametrize(
    "date,time,gender,at,number",
    [
        ("2000-06-12", "07:30", "女", None, 2411),
        ("2000-06-01", "11:30", "男", None, 2514),
        ("2000-06-05", "03:30", "男", None, 2914),
        ("2000-06-12", "07:30", "女", "2033-08-05T11:41:23.090575+08:00", 2209),
        ("2000-06-12", "07:30", "女", "2099-08-05T12:06:49.602995+08:00", 2221),
        ("2000-06-12", "07:30", "女", "2012-10-08T15:51:42.708853+08:00", 3314),
    ],
)
def test_native_gold_rereadings_keep_all_four_batches_across_surfaces(
    date, time, gender, at, number, rest, tmp_path, capsys
):
    import json
    from pathlib import Path

    reference = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/canping_gold_rereading_v1/reference.json"
        ).read_text()
    )
    kind = "luck" if at else "male" if gender == "男" else "female"
    expected = next(
        c for c in reference["cells"] if (c["number"], c["kind"]) == (number, kind)
    )
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    if at:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        v = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = v["selectionShun"]
        assert v["numShun"] == selected["number"] == number
        assert (
            v["textShun"] == expected["text"]
            and selected["cell_status"] == expected["state"]
        )
        assert selected["element"] == "金" and selected["kind"] == kind
        assert selected["source_pdf_page"] == expected["pdf_page"]
        assert selected["column"] == (
            "lower_shared_luck"
            if at
            else "upper_male" if gender == "男" else "middle_female"
        )
        assert "number_attribution_status" not in selected
        revision = selected["reading_revision"]
        assert revision["rereading_id"] == reference["fixture_id"]
        assert revision["previous_collation_version"] == "1.9.0"
        assert revision["previous_text"] == expected["previous_text"]
        assert revision["previous_cell_status"] == "source_reading_uncertain"
        assert ("editorial_unknown_marker" in selected) == ("□" in expected["text"])
        assert "同馆藏原图复读，旧疑读另存" in output["snapshot_text"]
        assert expected["text"] in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        summary = evidence["canping_text_collation"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == v
        assert summary["version"] == "1.11.0" and summary["collated_cells"] == 1123
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["rereading_witness"]["resolved_cells"] == 30
        assert (
            summary["additional_rereading_witnesses"][0]["fixture_id"]
            == "canping_fire_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][0]["resolved_cells"] == 6
        assert len(summary["additional_rereading_witnesses"]) == 4
        assert (
            summary["additional_rereading_witnesses"][1]["fixture_id"]
            == "canping_wood_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][1]["resolved_cells"] == 3
        witness = next(
            w
            for w in summary["additional_rereading_witnesses"]
            if w["fixture_id"] == reference["fixture_id"]
        )
        assert witness["fixture_id"] == reference["fixture_id"]
        assert witness["resolved_cells"] == 4 and witness["still_uncertain_cells"] == 11
        assert (
            witness["new_numbered_cells_examined"]
            == witness["new_independent_reviews"]
            == 0
        )
        assert (
            witness["native_region_count"] == 28 and witness["reused_region_count"] == 0
        )
        assert len(witness["pages"]) == 7
        assert summary["number_reading_witness"]["headers_still_uncertain"] == 6
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]


@pytest.mark.parametrize(
    "date,time,gender,at,number,use_true,lon,zone",
    [
        ("1990-06-02", "19:30", "女", None, 3377, False, None, "Asia/Shanghai"),
        ("1990-06-03", "21:30", "男", None, 3379, False, None, "Asia/Shanghai"),
        (
            "2028-04-06",
            "09:33",
            "女",
            "2032-08-05T05:45:16.526525+08:00",
            2460,
            True,
            121.46666667,
            "+08:00",
        ),
        (
            "1990-06-02",
            "19:30",
            "女",
            "2011-08-06T03:27:40.256321+08:00",
            3363,
            False,
            None,
            "Asia/Shanghai",
        ),
    ],
)
def test_native_earth_rereadings_and_unchanged_comparison_across_surfaces(
    date, time, gender, at, number, use_true, lon, zone, rest, tmp_path, capsys
):
    import json
    from pathlib import Path

    reference = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/canping_earth_rereading_v1/reference.json"
        ).read_text()
    )
    kind = "luck" if at else "male" if gender == "男" else "female"
    expected = next(
        c
        for c in reference["cells"] + reference["comparison_cells"]
        if (c["number"], c["kind"]) == (number, kind)
    )
    spec = SPECS["canping"]
    payload = {**INPUT, "date": date, "time": time, "gender": gender}
    payload.update(use_true_solar_time=use_true, zone=zone)
    if lon is not None:
        payload["lon"] = str(lon)
    if at:
        payload["analysis_datetime"] = at
    fields = [
        "benming.verses",
        "canping_timing.selected",
        "numerology_evidence.canping_text_collation",
        "numerology_evidence.selected_texts",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        v = (
            output["canping_timing"]["selected"]["verses"]
            if at
            else output["benming"]["verses"]
        )
        selected = v["selectionShun"]
        assert v["numShun"] == selected["number"] == number
        assert (
            v["textShun"] == expected["text"]
            and selected["cell_status"] == expected["state"]
        )
        assert selected["element"] == "土" and selected["kind"] == kind
        assert selected["source_pdf_page"] == expected["pdf_page"]
        assert selected["column"] == (
            "lower_shared_luck"
            if at
            else "upper_male" if gender == "男" else "middle_female"
        )
        assert "number_attribution_status" not in selected
        if number == 3379:
            assert "reading_revision" not in selected
            assert v["textShun"] == "八尺長燈檠，清光射白晝。"
        else:
            revision = selected["reading_revision"]
            assert revision["rereading_id"] == reference["fixture_id"]
            assert revision["previous_collation_version"] == "1.10.0"
            assert revision["previous_text"] == expected["previous_text"]
            assert revision["previous_cell_status"] == "source_reading_uncertain"
            assert ("editorial_unknown_marker" in selected) == ("□" in expected["text"])
            assert "同馆藏原图复读，旧疑读另存" in output["snapshot_text"]
        assert expected["text"] in output["snapshot_text"]
        evidence = output["numerology_evidence"]
        summary = evidence["canping_text_collation"]
        assert evidence["selected_texts"][-1 if at else 0]["verses"] == v
        assert summary["version"] == "1.11.0" and summary["collated_cells"] == 1123
        assert summary["unresolved_reading_cells"] == summary["pending_cells"] == 47
        assert summary["rereading_witness"]["resolved_cells"] == 30
        assert (
            summary["additional_rereading_witnesses"][0]["fixture_id"]
            == "canping_fire_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][0]["resolved_cells"] == 6
        assert len(summary["additional_rereading_witnesses"]) == 4
        assert (
            summary["additional_rereading_witnesses"][1]["fixture_id"]
            == "canping_wood_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][1]["resolved_cells"] == 3
        assert (
            summary["additional_rereading_witnesses"][2]["fixture_id"]
            == "canping_gold_native_rereading_v1"
        )
        assert summary["additional_rereading_witnesses"][2]["resolved_cells"] == 4
        witness = next(
            w
            for w in summary["additional_rereading_witnesses"]
            if w["fixture_id"] == reference["fixture_id"]
        )
        assert witness["fixture_id"] == reference["fixture_id"]
        assert witness["resolved_cells"] == 1 and witness["still_uncertain_cells"] == 2
        assert (
            witness["new_numbered_cells_examined"]
            == witness["new_independent_reviews"]
            == 0
        )
        assert (
            witness["native_region_count"] == 12 and witness["reused_region_count"] == 0
        )
        assert len(witness["pages"]) == 3
        assert summary["number_reading_witness"]["headers_still_uncertain"] == 6
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_text_selection_v1"
        )
        assert trace["collation_sha256"] == summary["sha256"]


@pytest.mark.parametrize(
    "fault", ["najia_table", "month_source", "line_source", "structure_source"]
)
def test_heluo_source_conflict_is_not_a_birth_input_error_on_three_surfaces(
    fault, rest, monkeypatch, tmp_path, capsys
):
    from copy import deepcopy

    from fatebridge.core import heluo, heluo_lines, heluo_months, heluo_structure

    spec = SPECS["heluo"]
    if fault == "najia_table":
        bad = deepcopy(heluo.NAJIA)
        bad["震"][-1] = "庚寅"
        monkeypatch.setattr(heluo, "NAJIA", bad)
        reason = "runtime_assignment_conflict"
    elif fault == "month_source":
        path = tmp_path / "invalid-month.json"
        path.write_text("{")
        heluo_months._collation.cache_clear()
        monkeypatch.setattr(heluo_months, "COLLATION_PATH", path)
        reason = "invalid_month_source_data"
    elif fault == "line_source":
        import json

        data = json.loads(heluo_lines.SOURCE_PATH.read_text())
        data["clauses"]["support"]["required_selected_yang"] = True
        path = tmp_path / "invalid-line-source.json"
        path.write_text(json.dumps(data, ensure_ascii=False))
        heluo_lines._source.cache_clear()
        monkeypatch.setattr(heluo_lines, "SOURCE_PATH", path)
        reason = "invalid_line_condition_source_data"
    else:
        import json

        data = json.loads(heluo_structure.SOURCE_PATH.read_text())
        data["source_case_reversed_name"] = "坤為地"
        path = tmp_path / "invalid-structure-source.json"
        path.write_text(json.dumps(data, ensure_ascii=False))
        heluo_structure._source.cache_clear()
        monkeypatch.setattr(heluo_structure, "SOURCE_PATH", path)
        reason = "invalid_body_structure_source_data"
    payload = {**INPUT, "date": "2026-11-12", "time": "09:33:00", "gender": "男"}
    flags = {"fields": ["analysis_type"], "strict_fields": True}
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", "analysis_type"), ("strict_fields", "true")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
    )
    protocol = asyncio.run(native(spec, {**payload, **flags}))
    assert response.status_code == 503 and code == 1 and protocol.is_error
    for output in (response.json(), local, protocol.structured_content):
        assert output["error_code"] == "numerology_source_inconsistent"
        assert output["retryable"] is False
        assert output["issues"] == [
            {
                "path": "runtime.numerology_sources",
                "code": reason,
            }
        ]
        assert "judge" not in output


@pytest.mark.parametrize("tool", ["heluo", "canping"])
@pytest.mark.parametrize("leaf_only", [False, True])
def test_numerology_historical_calendar_policy_on_three_surfaces(
    tool, leaf_only, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    # A synthetic ancient date with a supplied clock/offset; no real birth claimed.
    payload = {
        **INPUT,
        "date": "1150-08-23",
        "time": "17:00",
        "gender": "男",
        "zone": "+08:00",
    }
    root = "numerology_evidence.birth_clock.calendar_policy"
    fields = (
        [root + ".input_calendar"]
        if leaf_only
        else [
            root,
            "numerology_evidence.rule_trace",
            "snapshot_text",
            "four_pillars.day",
        ]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        policy = output["numerology_evidence"]["birth_clock"]["calendar_policy"]
        assert policy["input_calendar"] == "proleptic_gregorian"
        if not leaf_only:
            assert policy["automatic_reform_cutover"] is False
            assert policy["historical_lunar_date_conversion"] is False
            assert policy["historical_official_calendar_reconstruction"] is False
            assert output["four_pillars"]["day"] == {"stem": "丙", "branch": "申"}
            assert "推算格里历" in output["snapshot_text"]
            clock_trace = next(
                t
                for t in output["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == "numerology_explicit_longitude_clock_v1"
            )
            assert clock_trace["facts"]["calendar_policy"] == policy


@pytest.mark.parametrize(
    "date,time,gender,matches",
    [
        ("1990-12-13", "01:30", "女", [True, False]),
        ("1991-07-13", "01:30", "女", [True, False]),
        ("1990-06-15", "09:33", "男", [False, False]),
        ("2000-05-15", "09:33", "男", [False, False]),
    ],
)
@pytest.mark.parametrize("phases_only", [False, True])
def test_heluo_body_structure_actual_bits_and_source_scope_on_three_surfaces(
    date, time, gender, matches, phases_only, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = dict(
        date=date,
        time=time,
        zone="Asia/Shanghai",
        gender=gender,
        use_true_solar_time=False,
    )
    fields = (
        ["judge.body_structure.phases"]
        if phases_only
        else evidence_views(spec)["body_structure"]["fields"]
        + ["judge.deTi", "snapshot_text"]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        spec.output_model.model_validate(out)
        evidence = out["judge"]["body_structure"]
        rows = evidence["phases"]
        assert [r["literal_case_match"] for r in rows] == matches
        for row in rows:
            assert row["record_count"] == len(row["records"]) == 8
            assert [r["arity"] for r in row["records"]] == [3, 3, 3, 3, 3, 3, 6, 6]
            for record in row["records"]:
                assert record["lines"] == [
                    row["input_lines"][p - 1] for p in record["original_positions"]
                ]
            assert row["whole_reversal"]["lines"] == row["input_lines"][::-1]
            if row["literal_case_match"]:
                assert row["literal_names_reproduced"] is True
                assert [r["name"] for r in row["records"]] == [
                    "艮",
                    "巽",
                    "震",
                    "兌",
                    "離",
                    "坎",
                    "天地否",
                    "地天泰",
                ]
            else:
                assert row["literal_names_reproduced"] is None
            if not phases_only:
                assert row["input_lines"] == out["chart"][row["phase"]]["lines"]
        if not phases_only:
            trace = next(
                r
                for r in out["numerology_evidence"]["rule_trace"]
                if r["rule_id"] == evidence["ruleset_id"]
            )
            assert trace["facts"] == evidence
            assert (
                evidence["complete_assessment"]
                is evidence["complete_futi_assessment"]
                is False
            )
            assert evidence["five_ming_terminology"]["selected_pillar"] is None
            assert out["judge"]["deTi"]["present"] is None
            assert "[卦体结构·渐卦原例取法]" in out["snapshot_text"]
            assert "八条记录含三爻体与六爻卦" in out["snapshot_text"]


@pytest.mark.parametrize("tool", ["heluo", "canping"])
@pytest.mark.parametrize("leaf_only", [False, True])
@pytest.mark.parametrize(
    "date,time,tst,lon,year,day",
    [
        ("2001-01-24", "09:33", False, None, "庚辰", None),
        ("2000-05-15", "23:30", False, None, "庚辰", "甲戌"),
        ("2000-05-16", "00:30", False, None, "庚辰", "甲戌"),
        ("2000-05-16", "00:10", True, 75, "庚辰", "癸酉"),
    ],
)
def test_numerology_pillar_links_selected_year_day_and_source_on_three_surfaces(
    tool, leaf_only, date, time, tst, lon, year, day, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=tst
    )
    if lon is not None:
        payload["lon"] = str(lon)
    fields = (
        ["numerology_evidence.pillar_links.links"]
        if leaf_only
        else evidence_views(spec)["pillar_links"]["fields"] + ["snapshot_text"]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        e = out["numerology_evidence"]["pillar_links"]
        rows = e["links"]
        assert [r["target"] for r in rows] == ["month", "hour"]
        assert rows[0]["basis_pillar"] == year
        if day is not None:
            assert rows[1]["basis_pillar"] == day
        assert all(
            r["matches"] and r["actual_pillar"] == r["expected_pillar"] for r in rows
        )
        if not leaf_only:
            assert e["pillars"] == {
                k: v["stem"] + v["branch"] for k, v in out["four_pillars"].items()
            }
            assert (
                e["all_links_match"] is True
                and e["complete_calendar_assessment"] is False
            )
            trace = next(
                r["facts"]
                for r in out["numerology_evidence"]["rule_trace"]
                if r["rule_id"] == e["ruleset_id"]
            )
            assert trace == e
            assert "[四柱干支衔接·卷七附法]" in out["snapshot_text"]
            assert "不据此证明原典年界、月界、子时换日" in out["snapshot_text"]


@pytest.mark.parametrize("tool", ["heluo", "canping"])
@pytest.mark.parametrize("target", ["month", "hour", "source"])
def test_numerology_computed_pillar_conflict_and_bad_source_are_internal_faults_on_three_surfaces(
    tool, target, rest, tmp_path, capsys, monkeypatch
):
    import importlib
    import json
    from dataclasses import replace

    from fatebridge.core import numerology_pillars as links

    adapter = importlib.import_module("fatebridge.core.local_techniques." + tool)
    if target == "source":
        data = json.loads(links.SOURCE_PATH.read_text())
        data["month_heads"] = []
        p = tmp_path / "bad-pillar-source.json"
        p.write_text(json.dumps(data))
        links._source.cache_clear()
        monkeypatch.setattr(links, "SOURCE_PATH", p)
        reason = "invalid_pillar_link_source_data"
    else:
        original = adapter._build_metaphysics_seed

        def bad_seed(*args, **kwargs):
            seed = original(*args, **kwargs)
            pillars = dict(seed.pillars)
            stem, branch = pillars[target]
            pillars[target] = (links.GAN[(links.GAN.index(stem) + 2) % 10], branch)
            return replace(seed, pillars=pillars)

        monkeypatch.setattr(adapter, "_build_metaphysics_seed", bad_seed)
        reason = "runtime_pillar_link_conflict"
    spec = SPECS[tool]
    payload = dict(
        date="2000-05-15",
        time="09:33",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", "analysis_type"), ("strict_fields", "true")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
    )
    protocol = asyncio.run(
        native(spec, {**payload, "fields": ["analysis_type"], "strict_fields": True})
    )
    assert response.status_code == 503 and code == 1 and protocol.is_error
    for out in [response.json(), local, protocol.structured_content]:
        assert (
            out["error_code"] == "numerology_source_inconsistent"
            and out["retryable"] is False
        )
        assert out["issues"] == [dict(path="runtime.numerology_sources", code=reason)]
        assert "four_pillars" not in out


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize(
    "date,time,phase,gua,line",
    [
        ("2000-01-02", "09:33", 1, "山水蒙", 3),
        ("2000-01-02", "15:33", 1, "水雷屯", 1),
        ("2000-01-08", "15:33", 0, "水雷屯", 4),
        ("2000-01-27", "00:30", 1, "山水蒙", 4),
    ],
)
def test_tunmeng_source_commentary_and_unselected_conditions_on_three_surfaces(
    texts_only, date, time, phase, gua, line, rest, tmp_path, capsys
):
    import json
    from pathlib import Path

    ref = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/heluo_tunmeng_v1/verified-readings.json"
        ).read_text()
    )
    expected = next(
        e for e in ref["entries"] if (e["hexagram"], e["line"]) == (gua, line)
    )
    spec = SPECS["heluo"]
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = (
        ["numerology_evidence.selected_texts"]
        if texts_only
        else evidence_views(spec)["selected_texts"]["fields"] + ["snapshot_text"]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        selected = out["numerology_evidence"]["selected_texts"][phase]
        text = selected["text"]
        assert text["commentary_sections"] == [
            dict(s, applicability=None) for s in expected["sections"]
        ]
        if not texts_only:
            e = out["numerology_evidence"]
            assert (selected["hexagram"], selected["line"]) == (gua, line)
            assert text["detail"] == "".join(s["text"] for s in expected["sections"])
            assert text["detail"] in out["snapshot_text"]
            assert text["commentary_branch_selection"]["selected_section_ids"] == []
            assert (
                text["text_provenance"]["commentary_pdf_pages"] == expected["pdf_pages"]
            )
            assert (
                e["commentary_collation"]["collated_line_commentaries"] == HEADER_COUNT
            )
            assert (
                e["commentary_collation"]["pending_line_commentaries"] == PENDING_COUNT
            )
            trace = next(
                t["facts"]
                for t in e["rule_trace"]
                if t["rule_id"] == "heluo_selected_line_collation_v1"
            )
            assert (
                trace["commentary_sha256"]
                == e["commentary_collation"]["sha256"]
                == text["text_provenance"]["commentary_sha256"]
            )
            assert trace["selections"][phase]["corpus_key"] == selected["corpus_key"]
            assert (
                trace["selections"][phase]["commentary_pdf_pages"]
                == expected["pdf_pages"]
            )


@pytest.mark.parametrize("layer", ["header", "commentary"])
def test_heluo_text_source_damage_is_not_a_birth_error_on_three_surfaces(
    layer, rest, tmp_path, capsys, monkeypatch
):
    import json

    from fatebridge.core import heluo_texts

    path_name, loader, reason = (
        ("COLLATION_PATH", heluo_texts._collation, "invalid_heluo_header_collation")
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            heluo_texts._commentary_collation,
            "invalid_heluo_commentary_collation",
        )
    )
    data = json.loads(getattr(heluo_texts, path_name).read_text())
    data["entries"].pop()
    p = tmp_path / "damaged-text-source.json"
    p.write_text(json.dumps(data))
    loader.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(heluo_texts, path_name, p)
            spec = SPECS["heluo"]
            payload = dict(
                date="2000-01-02",
                time="09:33",
                zone="+08:00",
                gender="男",
                use_true_solar_time=False,
            )
            response = rest.post(
                spec.rest_path,
                json=payload,
                params=[("fields", "analysis_type"), ("strict_fields", "true")],
            )
            code, local = call_cli(
                spec,
                payload,
                tmp_path,
                capsys,
                flags=["--fields", "analysis_type", "--strict-fields", "true"],
            )
            protocol = asyncio.run(
                native(
                    spec,
                    {**payload, "fields": ["analysis_type"], "strict_fields": True},
                )
            )
            assert response.status_code == 503 and code == 1 and protocol.is_error
            for out in [response.json(), local, protocol.structured_content]:
                assert (
                    out["error_code"] == "numerology_source_inconsistent"
                    and out["retryable"] is False
                )
                assert out["issues"] == [
                    dict(path="runtime.numerology_sources", code=reason)
                ]
                assert "chart" not in out
    finally:
        loader.cache_clear()


@pytest.mark.parametrize("context_only", [False, True])
@pytest.mark.parametrize(
    "date,time,tst,year,gz",
    [
        ("2001-01-24", "09:33", False, 2000, "庚辰"),
        ("2000-01-02", "09:33", False, 1999, "己卯"),
        ("2000-05-15", "23:30", False, 2000, "庚辰"),
        ("2000-05-16", "00:10", True, 2000, "庚辰"),
    ],
)
def test_heluo_clock_profile_and_birth_year_context_on_three_surfaces(
    context_only, date, time, tst, year, gz, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = dict(
        date=date,
        time=time,
        zone="+08:00",
        gender="男",
        use_true_solar_time=tst,
        analysis_year=2026,
        month_index=7,
        day_index=13,
    )
    if tst:
        payload["lon"] = "75"
    fields = (
        ["heluo_timing.year_context"]
        if context_only
        else evidence_views(spec)["clock_basis"]["fields"]
        + ["chart.cycleYear", "four_pillars.year", "snapshot_text"]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        context = out["heluo_timing"]["year_context"]
        assert (
            context["cycle_year"] == year
            and context["birth_ganzhi"] == context["expected_ganzhi"] == gz
            and context["matches"] is True
        )
        if not context_only:
            assert (
                out["chart"]["cycleYear"] == year
                and "".join(out["four_pillars"]["year"][k] for k in ["stem", "branch"])
                == gz
            )
            source = out["heluo_timing"]["source_clock"]
            assert (
                source["day_ke"] == 100
                and sum(b["length_ke"] for b in source["branch_lengths"]) == 100
            )
            assert (
                source["physical_clock_applied"]
                is source["calendar_mapping_complete"]
                is False
            )
            assert (
                source["physical_origin_branch"]
                is source["daily_extra_literal"]["fen_per_ke"]
                is None
            )
            assert source["equal_shi_projection"]["source_fen_scale_verified"] is False
            shift = source["branch_shift_projection"]
            assert shift["extra_ke"] == 500
            assert shift["total_source_days"] == dict(numerator=365, denominator=1)
            assert shift["branch_start_only"] is shift["derived_only"] is True
            assert (
                shift["source_fen_scale_selected"]
                is shift["daily_internal_distribution_resolved"]
                is False
            )
            trace = next(
                t["facts"]
                for t in out["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == source["ruleset_id"]
            )
            assert trace == dict(clock_profile=source, year_context=context)
            assert (
                "[卷一百刻原式]" in out["snapshot_text"]
                and "每刻18分不作原典默认值" in out["snapshot_text"]
            )


@pytest.mark.parametrize("fault", ["year", "source"])
def test_heluo_year_or_clock_source_failure_is_not_user_birth_fault(
    fault, rest, tmp_path, capsys, monkeypatch
):
    import importlib
    import json

    from fatebridge.core import heluo_clock

    adapter = importlib.import_module("fatebridge.core.local_techniques.heluo")
    if fault == "year":
        original = adapter._heluo_calculate

        def wrong(*args, **kwargs):
            chart = original(*args, **kwargs)
            chart["cycleYear"] += 1
            return chart

        monkeypatch.setattr(adapter, "_heluo_calculate", wrong)
        reason = "runtime_heluo_year_context_conflict"
    else:
        data = json.loads(heluo_clock.SOURCE_PATH.read_text())
        data["source_fen_per_ke"] = 18
        p = tmp_path / "fitted-clock.json"
        p.write_text(json.dumps(data))
        heluo_clock._source.cache_clear()
        monkeypatch.setattr(heluo_clock, "SOURCE_PATH", p)
        reason = "invalid_heluo_clock_source"
    try:
        spec = SPECS["heluo"]
        payload = dict(
            date="2000-05-15",
            time="09:33",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", "analysis_type"), ("strict_fields", "true")],
        )
        code, local = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "analysis_type", "--strict-fields", "true"],
        )
        protocol = asyncio.run(
            native(
                spec, {**payload, "fields": ["analysis_type"], "strict_fields": True}
            )
        )
        assert response.status_code == 503 and code == 1 and protocol.is_error
        for out in [response.json(), local, protocol.structured_content]:
            assert (
                out["error_code"] == "numerology_source_inconsistent"
                and out["retryable"] is False
            )
            assert out["issues"] == [
                dict(path="runtime.numerology_sources", code=reason)
            ]
            assert "chart" not in out
    finally:
        heluo_clock._source.cache_clear()


@pytest.mark.parametrize("selected_only", [False, True])
@pytest.mark.parametrize(
    "date,term,gua,pos,raw_conflict",
    [
        ("2026-01-06", "小寒", "坎為水", 2, "火澤睽"),
        ("2026-09-09", "白露", "離為火", 6, "巽為風"),
        ("2026-09-25", "秋分", "兌為澤", 1, "山火賁"),
        ("2026-11-10", "立冬", "兌為澤", 4, "水火既濟"),
    ],
)
def test_heluo_jiehou_terms_literals_and_both_models_on_three_surfaces(
    selected_only, date, term, gua, pos, raw_conflict, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = dict(
        date=date,
        time="12:00:00",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    fields = (
        [
            "jiehou_evidence.selected_term_gua.position",
            "jiehou_evidence.upstream_term_label",
        ]
        if selected_only
        else evidence_views(spec)["jiehou"]["fields"] + ["snapshot_text"]
    )
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("response_char_limit", "0"),
    ]
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        p = out["jiehou_evidence"]
        assert (
            p["upstream_term_label"] == term
            and p["selected_term_gua"]["position"] == pos
        )
        if not selected_only:
            assert p["selected_term_gua"]["gua"] == gua
            assert p["upstream_term_label"] == out["solar_term"]["term"]
            assert p["anchor_utc"] == out["solar_term"]["anchor_utc"]
            assert (
                p["selected_hou"]
                is p["huagong_assessment"]
                is p["selected_reconstruction_model"]
                is None
            )
            assert (
                p["historical_term_instants_established"]
                is p["hou_physical_date_mapping_complete"]
                is False
            )
            bad = next(r for r in p["literal_hou_group"] if r["gua"] == raw_conflict)
            assert (
                bad["yao_polarity_agrees"] is False
                and bad["raw_yao"] != bad["canonical_yao"]
            )
            assert [
                m["caption_difference_count"] for m in p["reconstruction_models"]
            ] == [3, 0]
            assert [
                m["term_start_gua_difference_count"] for m in p["reconstruction_models"]
            ] == [1, 11]
            trace = next(
                t["facts"]
                for t in out["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == p["ruleset_id"]
            )
            assert trace == p
            assert (
                f"{gua}，" in out["snapshot_text"]
                and f"{raw_conflict}原印{bad['raw_yao']}" in out["snapshot_text"]
            )


@pytest.mark.parametrize("fault", ["source", "context"])
def test_heluo_jiehou_source_or_context_fault_on_three_surfaces(
    fault, rest, tmp_path, capsys, monkeypatch
):
    import importlib
    import json

    from fatebridge.core import heluo_jiehou as jh

    adapter = importlib.import_module("fatebridge.core.local_techniques.heluo")
    if fault == "source":
        d = json.loads(jh.SOURCE_PATH.read_text())
        d["hou_rows"][5]["raw_yao"] = "初九"
        p = tmp_path / "corrected-primary.json"
        p.write_text(json.dumps(d, ensure_ascii=False))
        jh._source.cache_clear()
        monkeypatch.setattr(jh, "SOURCE_PATH", p)
        reason = "invalid_heluo_jiehou_source"
    else:
        original = adapter._heluo_solar_term

        def inconsistent(*args, **kwargs):
            st = original(*args, **kwargs)
            st["quarter"] = "兌"
            return st

        monkeypatch.setattr(adapter, "_heluo_solar_term", inconsistent)
        reason = "runtime_heluo_jiehou_context_conflict"
    try:
        spec = SPECS["heluo"]
        payload = dict(
            date="2026-01-06",
            time="12:00:00",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", "analysis_type"), ("strict_fields", "true")],
        )
        code, local = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "analysis_type", "--strict-fields", "true"],
        )
        protocol = asyncio.run(
            native(
                spec, {**payload, "fields": ["analysis_type"], "strict_fields": True}
            )
        )
        assert response.status_code == 503 and code == 1 and protocol.is_error
        for out in [response.json(), local, protocol.structured_content]:
            assert (
                out["error_code"] == "numerology_source_inconsistent"
                and out["retryable"] is False
            )
            assert out["issues"] == [
                dict(path="runtime.numerology_sources", code=reason)
            ]
    finally:
        jh._source.cache_clear()


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize(
    "date,time,phase,gua,line,excerpt",
    [
        ("2000-01-11", "00:30", 0, "水天需", 1, "恬淡之官"),
        ("2000-01-09", "15:33", 0, "天水訟", 1, "起次訟"),
        ("2000-03-07", "15:33", 1, "水天需", 2, "言字、終字"),
        ("2000-09-01", "15:33", 1, "水天需", 3, "自貽伊戚"),
    ],
)
def test_heluo_xusong_commentary_and_content_identity_on_three_surfaces(
    texts_only, date, time, phase, gua, line, excerpt, rest, tmp_path, capsys
):
    from fatebridge.core.heluo_texts import (
        COMMENTARY_CONTENT_SHA256,
        HEADER_CONTENT_SHA256,
    )

    spec = SPECS["heluo"]
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = (
        ["numerology_evidence.selected_texts"]
        if texts_only
        else [
            "numerology_evidence.selected_texts",
            "numerology_evidence.commentary_collation",
            "numerology_evidence.yaoci_collation",
            "numerology_evidence.rulesets",
            "numerology_evidence.rule_trace",
            "snapshot_text",
        ]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        e = out["numerology_evidence"]
        selected = e["selected_texts"][phase]
        t = selected["text"]
        p = t["text_provenance"]
        assert (selected["hexagram"], selected["line"]) == (gua, line)
        assert (
            excerpt in t["detail"]
            and p["commentary_content_sha256"] == COMMENTARY_CONTENT_SHA256
        )
        assert p["header_content_sha256"] == HEADER_CONTENT_SHA256
        assert all(s["applicability"] is None for s in t["commentary_sections"])
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        if not texts_only:
            assert (
                e["commentary_collation"]["collated_line_commentaries"],
                e["commentary_collation"]["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)
            assert (
                e["commentary_collation"]["content_sha256"] == COMMENTARY_CONTENT_SHA256
            )
            trace = next(
                v["facts"]
                for v in e["rule_trace"]
                if v["rule_id"] == "heluo_selected_line_collation_v1"
            )
            assert trace["commentary_content_sha256"] == COMMENTARY_CONTENT_SHA256
            assert trace["header_content_sha256"] == HEADER_CONTENT_SHA256
            rule = next(
                v for v in e["rulesets"] if v["ruleset_id"] == COMMENTARY_RULESET_ID
            )
            assert (
                f"{HEADER_COUNT}条" in rule["source_title"]
                and rule["source_content_sha256"] == COMMENTARY_CONTENT_SHA256
            )
            assert t["detail"] in out["snapshot_text"]


@pytest.mark.parametrize("layer", ["header", "commentary"])
@pytest.mark.parametrize("fault", ["nonempty_replacement", "swapped_content"])
def test_heluo_nonempty_source_tamper_is_rejected_on_three_surfaces(
    layer, fault, rest, tmp_path, capsys, monkeypatch
):
    import json

    from fatebridge.core import heluo_texts as ht

    attr, loader, reason = (
        ("COLLATION_PATH", ht._collation, "invalid_heluo_header_collation")
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            ht._commentary_collation,
            "invalid_heluo_commentary_collation",
        )
    )
    data = json.loads(getattr(ht, attr).read_text())
    if layer == "header":
        if fault == "swapped_content":
            data["entries"][0]["yaoci"], data["entries"][1]["yaoci"] = (
                data["entries"][1]["yaoci"],
                data["entries"][0]["yaoci"],
            )
        else:
            data["entries"][0]["yaoci"] = "非原典标题"
    else:
        s = data["entries"][0]["sections"]
        if fault == "swapped_content":
            s[1]["text"], s[2]["text"] = s[2]["text"], s[1]["text"]
        else:
            s[1]["text"] = "葉者非原典正文。"
    path = tmp_path / "nonempty-source.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    loader.cache_clear()
    try:
        monkeypatch.setattr(ht, attr, path)
        spec = SPECS["heluo"]
        payload = dict(
            date="2000-01-11",
            time="00:30",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", "analysis_type"), ("strict_fields", "true")],
        )
        code, local = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "analysis_type", "--strict-fields", "true"],
        )
        protocol = asyncio.run(
            native(
                spec, {**payload, "fields": ["analysis_type"], "strict_fields": True}
            )
        )
        assert response.status_code == 503 and code == 1 and protocol.is_error
        for out in [response.json(), local, protocol.structured_content]:
            assert (
                out["error_code"] == "numerology_source_inconsistent"
                and out["retryable"] is False
            )
            assert out["issues"] == [
                dict(path="runtime.numerology_sources", code=reason)
            ]
    finally:
        loader.cache_clear()


@pytest.mark.parametrize(
    "date,time,expected,direct",
    [
        (
            "2000-01-01",
            "09:33",
            [[False, True], [False, True]],
            [[True, False], [False, True]],
        ),
        (
            "2000-01-11",
            "00:30",
            [[False, False], [True, False]],
            [[True, False], [True, True]],
        ),
        (
            "2000-03-07",
            "15:33",
            [[False, False], [False, False]],
            [[False, False], [False, False]],
        ),
        (
            "2000-09-01",
            "15:33",
            [[True, False], [False, False]],
            [[False, False], [False, False]],
        ),
    ],
)
@pytest.mark.parametrize("phases_only", [False, True])
def test_heluo_yuanqi_missing_original_premise_on_three_surfaces(
    date, time, expected, direct, phases_only, rest, tmp_path, capsys
):
    from fatebridge.core.heluo_opposition import CONTENT_SHA256, RULESET_ID

    spec = SPECS["heluo"]
    payload = dict(
        date=date, time=time, zone="+08:00", gender="男", use_true_solar_time=False
    )
    fields = (
        ["judge.qi_phases.yuanqi_opposition.phases"]
        if phases_only
        else [
            "judge.qi_phases",
            "judge.fanYuan",
            "judge.fanYuan_policy",
            "numerology_evidence.rulesets",
            "numerology_evidence.rule_trace",
            "snapshot_text",
        ]
    )
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        opposition = out["judge"]["qi_phases"]["yuanqi_opposition"]
        assert [
            [c["condition_match"] for c in p["conditions"]]
            for p in opposition["phases"]
        ] == expected
        assert [
            [c["direct_only_condition_match"] for c in p["conditions"]]
            for p in opposition["phases"]
        ] == direct
        assert all(
            c["rescue_match"] is None
            for p in opposition["phases"]
            for c in p["conditions"]
        )
        if not phases_only:
            assert opposition["content_sha256"] == CONTENT_SHA256
            assert opposition["full_rescue_assessment"] is False
            trace = next(
                t
                for t in out["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == RULESET_ID
            )
            assert trace["facts"] == opposition
            assert any(
                r["ruleset_id"] == RULESET_ID
                and r["source_content_sha256"] == CONTENT_SHA256
                for r in out["numerology_evidence"]["rulesets"]
            )
            assert "[元气相反·无正而有反前提]" in out["snapshot_text"]
            assert "反天元气候选" in out["snapshot_text"]


@pytest.mark.parametrize("fault", ["resource", "runtime_mapping"])
def test_heluo_yuanqi_source_conflicts_fail_before_projection_on_three_surfaces(
    fault, rest, tmp_path, capsys, monkeypatch
):
    import json

    from fatebridge.core import heluo
    from fatebridge.core import heluo_opposition as op

    op._source.cache_clear()
    if fault == "resource":
        data = json.loads(op.SOURCE_PATH.read_text())
        data["absence_literal"] = "有反就是相反"
        path = tmp_path / "forged-opposition.json"
        path.write_text(json.dumps(data, ensure_ascii=False))
        monkeypatch.setattr(op, "SOURCE_PATH", path)
        reason = "invalid_heluo_opposition_source"
    else:
        monkeypatch.setitem(heluo.GAN_FAN, "己", "離")
        reason = "runtime_heluo_yuanqi_context_conflict"
    try:
        spec = SPECS["heluo"]
        payload = dict(
            date="2000-01-11",
            time="00:30",
            zone="+08:00",
            gender="男",
            use_true_solar_time=False,
        )
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", "analysis_type"), ("strict_fields", "true")],
        )
        code, local = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "analysis_type", "--strict-fields", "true"],
        )
        protocol = asyncio.run(
            native(
                spec, {**payload, "fields": ["analysis_type"], "strict_fields": True}
            )
        )
        assert response.status_code == 503 and code == 1 and protocol.is_error
        for result in [response.json(), local, protocol.structured_content]:
            assert (
                result["error_code"] == "numerology_source_inconsistent"
                and result["retryable"] is False
            )
            assert result["issues"] == [
                dict(path="runtime.numerology_sources", code=reason)
            ]
    finally:
        op._source.cache_clear()


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize(
    "date,time,zone,utc_year",
    [
        ("1800-01-01", "00:30", "+14:00", 1799),
        ("1800-07-01", "12:00", "UTC", 1800),
        ("2200-01-01", "12:00", "UTC", 2200),
        ("2200-12-31", "23:30", "-02:00", 2201),
    ],
)
def test_heluo_solar_endpoint_context_on_three_surfaces(
    mode, date, time, zone, utc_year, monkeypatch, rest, tmp_path, capsys
):
    from datetime import datetime

    from fatebridge.core.heluo_solar_context import POLICY_ID

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    empty = tmp_path.parent / "heluo-solar-shared-empty"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    spec = SPECS["heluo"]
    payload = dict(
        date=date, time=time, zone=zone, gender="男", use_true_solar_time=False
    )
    fields = [
        "solar_term",
        "calendar_context.current_solar_term",
        "judge.seasonal_numbers",
        "numerology_evidence.rule_trace",
        "snapshot_text",
    ]
    outputs = projected_outputs(spec, payload, fields, rest, tmp_path, capsys)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        c = out["solar_term"]["boundary_context"]
        assert (
            c["context_local_year"] == int(date[:4])
            and c["calendar_context_match"] is True
        )
        assert datetime.fromisoformat(c["birth_instant_utc"]).year == utc_year
        assert (
            c["dependencies"][0]["record"]
            == out["calendar_context"]["current_solar_term"]
        )
        assert {r["record"]["ephemeris_model"] for r in c["dependencies"]} == {
            "fatebridge_de440_solar_v1"
        }
        seasonal = out["judge"]["seasonal_numbers"]
        assert seasonal["context_local_year"] == int(date[:4])
        assert all(
            w[e + "_source"]["ephemeris_model"] == "fatebridge_de440_solar_v1"
            for w in seasonal["seasonal_windows"]
            for e in ["start", "end"]
        )
        assert (
            next(
                t["facts"]
                for t in out["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == POLICY_ID
            )
            == c
        )
        assert "[所用节气与至点来源]" in out["snapshot_text"]


@pytest.mark.parametrize("fault", ["rough_source", "classification"])
def test_heluo_solar_context_fault_cannot_hide_behind_projection(
    fault, monkeypatch, rest, tmp_path, capsys
):
    from dataclasses import replace

    from fatebridge.core import heluo_solar_context as source
    from fatebridge.core.local_techniques import heluo as adapter

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    if fault == "rough_source":
        original = source._term_window
        monkeypatch.setattr(
            source,
            "_term_window",
            lambda a, z: [
                replace(
                    t,
                    resolution_provider="linear_1900_fallback",
                    ephemeris_model="unknown",
                )
                for t in original(a, z)
            ],
        )
    else:
        original = adapter._heluo_solar_term

        def wrong(*args, **kwargs):
            r = original(*args, **kwargs)
            r["yang_ling"] = not r["yang_ling"]
            return r

        monkeypatch.setattr(adapter, "_heluo_solar_term", wrong)
    spec = SPECS["heluo"]
    payload = dict(
        date="2000-01-11",
        time="00:30",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", "analysis_type"), ("strict_fields", "true")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
    )
    protocol = asyncio.run(
        native(spec, {**payload, "fields": ["analysis_type"], "strict_fields": True})
    )
    assert response.status_code == 503 and code == 1 and protocol.is_error
    for out in [response.json(), local, protocol.structured_content]:
        assert (
            out["error_code"] == "numerology_source_inconsistent"
            and out["retryable"] is False
        )
        assert out["issues"] == [
            dict(
                path="runtime.numerology_sources",
                code="runtime_heluo_solar_context_conflict",
            )
        ]
