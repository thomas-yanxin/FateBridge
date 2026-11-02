"""Pinned Jingben ordinals, independent courses, missing facts and real ports."""

import asyncio
import copy

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import OutputContractError, validate_output
from fatebridge.core.metaphysics.jinkou_year_fate import ordinal_year_fate
from fatebridge.core.output_chinese import Jinkou, JinkouYearFate
from fatebridge.core.requests.metaphysics import JinkouAnalysisRequest
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from scripts.audit_jinkou_year_fate import course_cases, references
from tests.golden.canonical import canonical_json
from tests.test_agentic_nested_outputs import AS_OF, SPECS, call_cli, native, rest

REF, _RAW, _ERRATA = references()
COURSE, CASES = course_cases()
SPEC = SPECS["jinkou"]


@pytest.mark.parametrize("case", REF["source_ordinal_examples"])
def test_printed_ordinal_examples(case):
    value = ordinal_year_fate(
        birth_year_ganzhi=case["birth_year_ganzhi"],
        age=case["age"],
        gender=case["gender"],
    )
    assert value["ganzhi"] == case["expected_ganzhi"]
    assert value["age_boundary_classically_verified"] is False
    assert value["comprehensive_year_fate_adjudicated"] is False


@pytest.mark.parametrize("case", REF["start_table"])
@pytest.mark.parametrize("sex,key", [("男", "male"), ("女", "female")])
def test_every_birth_xun_has_its_own_printed_start(case, sex, key):
    value = ordinal_year_fate(birth_year_ganzhi=case["birth_xun"], age=1, gender=sex)
    assert value["ganzhi"] == case[key]


@pytest.mark.parametrize(
    "born,age,sex,missing",
    [
        (None, None, None, ["birth_year_ganzhi", "year_fate_age", "gender"]),
        ("甲午", 20, "未知", ["gender"]),
        ("甲午", None, "male", ["year_fate_age"]),
        (None, 20, "female", ["birth_year_ganzhi"]),
    ],
)
def test_missing_facts_are_retained_without_inference(born, age, sex, missing):
    value = ordinal_year_fate(birth_year_ganzhi=born, age=age, gender=sex)
    assert value["missing_inputs"] == missing and value["status"] == "missing_inputs"
    assert value["ganzhi"] is None and value["branch"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"birth_year_ganzhi": "甲丑"},
        {"birth_year_ganzhi": "2026"},
        {"birth_year_ganzhi": 2026},
        {"year_fate_age": 0},
        {"year_fate_age": True},
        {"year_fate_age": "20"},
        {"year_fate_age": 151},
        {"natal_branch": "子"},
    ],
)
def test_invalid_or_contradictory_explicit_facts_rejected(change):
    with pytest.raises(ValidationError):
        JinkouAnalysisRequest.model_validate(
            {**COURSE["calendar"], "gender": "男", **change}
        )


@pytest.fixture(scope="module")
def complete():
    value = calculate_jinkou_analysis(
        **COURSE["calendar"], gender="男", is_diurnal=True
    )
    SPEC.output_model.model_validate(value)
    return value


@pytest.mark.parametrize(
    "fault",
    [
        "age",
        "ganzhi",
        "branch",
        "gender",
        "course_ground",
        "observed_ground",
        "course_month",
        "course_diurnal",
        "course_policy",
        "false_cert",
        "numeric_cert",
        "main_source",
        "course_source",
        "drop_course",
        "natal",
    ],
)
def test_copresent_year_fate_facts_cannot_contradict_the_course(complete, fault):
    v = copy.deepcopy(complete["jinkou"])
    y = v["year_fate"]
    if fault == "age":
        y["age_ordinal"] = 21
    elif fault == "ganzhi":
        y["ganzhi"] = "丙辰"
    elif fault == "branch":
        y["branch"] = "辰"
    elif fault == "gender":
        y["gender"] = "女"
    elif fault == "course_ground":
        y["course"]["overview"]["di_fen"] = "辰"
    elif fault == "observed_ground":
        y["course"]["overview"]["di_fen_source"] = "explicit"
    elif fault == "course_month":
        y["course"]["overview"]["month_general"]["branch"] = "亥"
    elif fault == "course_diurnal":
        y["course"]["overview"]["is_diurnal"] = False
    elif fault == "course_policy":
        y["course"]["calendar_policy"]["scope"] = "another calendar"
    elif fault == "false_cert":
        y["comprehensive_year_fate_adjudicated"] = True
    elif fault == "numeric_cert":
        y["age_boundary_classically_verified"] = 0
    elif fault in ("main_source", "course_source"):
        target = v if fault == "main_source" else y["course"]
        target["relations"]["si_jue"]["natal"]["input_source"] = "explicit_natal_branch"
        for trace in target["rule_trace"]:
            if trace["rule_id"] == "jinkou.jingben_relations":
                trace["result"]["si_jue"]["natal"][
                    "input_source"
                ] = "explicit_natal_branch"
    elif fault == "drop_course":
        y["course"] = None
    else:
        y["natal_branch"] = "子"
    with pytest.raises(ValidationError):
        Jinkou.model_validate(v)


@pytest.mark.parametrize(
    "payload",
    [
        {"ganzhi": "乙卯"},
        {"course": {"overview": {"di_fen": "卯"}}},
        {"status": "missing_inputs", "course": None},
    ],
)
def test_sparse_projections_do_not_invent_omitted_inputs(payload):
    JinkouYearFate.model_validate(payload)


@pytest.mark.parametrize(
    "fault",
    ["omit_year_fate", "omit_course_rows", "omit_nullable_birth", "reuse_another_day"],
)
def test_complete_business_cannot_hide_annual_inputs_or_reuse_another_day(
    complete, fault
):
    body = copy.deepcopy(complete)
    y = body["jinkou"]["year_fate"]
    if fault == "omit_year_fate":
        del body["jinkou"]["year_fate"]
    elif fault == "omit_course_rows":
        del y["course"]["rows"]
    elif fault == "omit_nullable_birth":
        del y["birth_year_ganzhi"]
    else:
        # Preserve the course's internal consistency while contradicting the
        # parent event's actual day; root anchors must catch this.
        other = calculate_jinkou_analysis(
            **{**COURSE["calendar"], "analysis_day": 9}, gender="男", is_diurnal=True
        )
        y["course"] = other["jinkou"]["year_fate"]["course"]
    with pytest.raises(OutputContractError):
        validate_output(SPEC, body)


@pytest.mark.parametrize("case", CASES)
def test_independent_year_course_and_real_rest_mcp_cli(case, rest, tmp_path, capsys):
    payload = {
        **COURSE["calendar"],
        "gender": case["gender"],
        "is_diurnal": case["is_diurnal"],
    }
    response = rest.post(
        SPEC.rest_path, json=payload, params={"as_of": AS_OF, "response_char_limit": 0}
    )
    protocol = asyncio.run(native(SPEC, payload))
    code, cli = call_cli(
        SPEC, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    facts = []
    for body in [response.json(), protocol.structured_content, cli]:
        SPEC.output_model.model_validate(body)
        y = body["jinkou"]["year_fate"]
        child = y["course"]
        assert y["ganzhi"] == case["year_ganzhi"]
        assert [r["content"] for r in child["rows"]] == case["positions"]
        assert child["overview"]["guishen"]["name"] == case["god"]
        assert child["overview"]["use_position"] == case["polarity_use"]
        assert child["overview"]["di_fen_source"] == "annual_branch_derived_course"
        assert (
            y["course_basis"] == "annual_branch_as_ground_reading"
            and y["course_ground_is_observed"] is False
        )
        assert (
            body["jinkou"]["overview"]["di_fen"] == "酉"
            and child["overview"]["di_fen"] == case["ground"]
        )
        assert (
            y["natal_branch"] == "午"
            and y["natal_branch_source"] == "explicit_birth_year_ganzhi"
        )
        assert (
            body["jinkou"]["relations"]["si_jue"]["natal"]["input_source"]
            == "explicit_birth_year_ganzhi"
        )
        assert (
            child["relations"]["si_jue"]["natal"]["input_source"]
            == "explicit_birth_year_ganzhi"
        )
        assert (
            "行年另课" in body["snapshot_text"] and "不能五合" in body["snapshot_text"]
        )
        facts.append(
            canonical_json(
                {"four_pillars": body["four_pillars"], "jinkou": body["jinkou"]}
            )
        )
    assert len(set(facts)) == 1


def test_unknown_sex_keeps_year_course_unknown_in_strict_three_port_view(
    rest, tmp_path, capsys
):
    from fatebridge.application.examples import evidence_views

    view = evidence_views(SPEC)["year_fate"]
    assert "purpose" in view and "jinkou.year_fate" in view["fields"]
    payload = {**COURSE["calendar"], "gender": "未知", "is_diurnal": False}
    fields = ["four_pillars", "jinkou.year_fate", "jinkou.overview.di_fen"]
    response = rest.post(
        SPEC.rest_path,
        json=payload,
        params=[("fields", name) for name in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("as_of", AS_OF),
            ("response_char_limit", "0"),
        ],
    )
    protocol = asyncio.run(
        native(
            SPEC,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        SPEC,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    facts = []
    for body in [response.json(), protocol.structured_content, cli]:
        y = body["jinkou"]["year_fate"]
        assert y["status"] == "missing_inputs" and y["missing_inputs"] == ["gender"]
        assert y["course"] is None and y["ganzhi"] is None
        assert (
            y["natal_branch"] == "午" and body["jinkou"]["overview"]["di_fen"] == "酉"
        )
        facts.append(
            canonical_json(
                {"four_pillars": body["four_pillars"], "jinkou": body["jinkou"]}
            )
        )
    assert len(set(facts)) == 1


def test_invalid_birth_ganzhi_is_rejected_by_all_actual_ports(rest, tmp_path, capsys):
    payload = {**COURSE["calendar"], "birth_year_ganzhi": "甲丑", "gender": "男"}
    response = rest.post(SPEC.rest_path, json=payload, params={"as_of": AS_OF})
    protocol = asyncio.run(native(SPEC, payload))
    code, _ = call_cli(SPEC, payload, tmp_path, capsys)
    assert response.status_code in (400, 422) and protocol.is_error and code != 0
