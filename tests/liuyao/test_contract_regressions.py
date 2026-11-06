"""Related contract regressions with shared imports; original cases retained."""

from datetime import date

import pytest

from scripts.liuyao import audit_liuyao_1900 as primary
from tests.liuyao.test_liuyao_civil_windows import PUBLIC, ROOT, assert_public_windows
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.support.result_delivery import assert_same_run_receipt
from tests.support.transports import SPECS, business, rest, surface_calls


def test_full_1900_supported_cohort_matches_frozen_primary_cells_and_day_anchor():
    result = primary.audit()
    assert result["primary_printed_date_count"] == 365
    assert result["unique_supported_date_count"] == 365
    assert result["excluded_before_supported_start"] == 0
    assert result["newly_supported_prefix_count"] == 30
    assert result["hko_1901_seam_passed"]
    assert result["selected_checks_passed"]
    assert sum(r["day_checks"] for r in result["reports"]) == 1460
    assert sum(r["lunar_checks"] for r in result["reports"]) == 730


def test_missing_lunar_and_wrong_days_cannot_shrink_the_primary_cohort(monkeypatch):
    monkeypatch.setattr(
        primary,
        "build_sixyao_result",
        lambda **kw: {
            "nongli": {"dayGanZi": "错误"},
            "calendar_context": {"lunar_calendar": None},
        },
    )
    result = primary.audit()
    assert result["unique_supported_date_count"] == 365
    assert sum(len(r["mismatches"]) for r in result["reports"]) == 1460
    assert sum(len(r["lunar_unavailable"]) for r in result["reports"]) == 730
    assert not result["selected_checks_passed"]


def test_reducing_the_production_supported_range_cannot_improve_acceptance(monkeypatch):
    monkeypatch.setattr(
        "fatebridge.core.almanac.LUNAR_SUPPORTED_SOLAR_START", date(1900, 2, 1)
    )
    with pytest.raises(ValueError, match="do not shrink"):
        primary.audit()


def test_primary_comparisons_cannot_pass_after_source_changes(monkeypatch):
    real_hashes = primary.hashes
    calls = 0

    def changed_hashes():
        nonlocal calls
        calls += 1
        values = real_hashes()
        if calls > 1:
            values["src/fatebridge/core/local_techniques/sixyao.py"] = "changed"
        return values

    monkeypatch.setattr(primary, "hashes", changed_hashes)
    report = primary.audit()
    assert all(not r["mismatches"] for r in report["reports"])
    assert not report["implementation_and_manifests_unchanged"]
    assert not report["selected_checks_passed"]


@pytest.mark.parametrize(
    "day,cessation,adverse,independent",
    [
        ("2004-06-02", False, None, True),
        ("2003-12-05", None, True, False),
        ("2000-08-22", None, None, False),
    ],
)
def test_earth_exception_public_calendar_contexts(
    day, cessation, adverse, independent, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="100100",
        changed_code="100101",
        focus_line=1,
    )
    root = "liuyao_evidence.conditional_analysis"
    for result in all_surfaces(
        payload,
        [root + ".cessation_conditions", root + ".role_effects", root + ".lines"],
        rest,
        tmp_path,
        capsys,
    ):
        detail = result["liuyao_evidence"]["conditional_analysis"]
        query = detail["cessation_conditions"]["lines"][5]
        assert query["changed"]["position_match"] is True
        assert query["changed"].get("condition_match") is cessation
        assert query["independent_support_present"] is independent
        assert query["total_rootlessness_established"] is False
        role = next(r for r in detail["role_effects"]["lines"] if r["position"] == 6)
        assert role["atom_values"]["changed_adverse"] is True
        assert role["conditional_atom_values"].get("changed_adverse") is adverse
        assert detail["lines"][5]["changed_stage"] == "绝"


def test_false_cessation_leaf_has_no_sibling_requirement(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.cessation_conditions.focus.changed.condition_match"
    for result in all_surfaces(
        dict(
            date="2004-06-02",
            time="12:00:00",
            gua_code="100100",
            changed_code="100101",
            focus_line=6,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert result["liuyao_evidence"]["conditional_analysis"][
            "cessation_conditions"
        ] == {"focus": {"changed": {"condition_match": False}}}


@pytest.mark.parametrize(
    "day,phrase",
    [("2004-06-02", "本项论生不论绝"), ("2000-08-22", "气根或反制尚待裁定")],
)
def test_same_run_text_tracks_qualified_cessation(
    day, phrase, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "cessation-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date=day,
        time="12:00:00",
        gua_code="100100",
        changed_code="100101",
        focus_line=1,
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert phrase in original["snapshot_text"]
        assert "第6爻戌土：本位变支巳见绝位" in original["snapshot_text"]


@pytest.mark.parametrize("case", PUBLIC["cases"], ids=lambda x: x["input"]["zone"])
@pytest.mark.parametrize("project", [False, True])
def test_true_utc_day_components_in_rest_native_mcp_cli(
    case, project, rest, tmp_path, capsys
):
    fields = [ROOT] if project else None
    for output in all_surfaces(case["input"], fields, rest, tmp_path, capsys):
        assert_public_windows(output, case)
        assert not output.get("projection_warnings")


@pytest.mark.parametrize(
    "case", [PUBLIC["cases"][0], PUBLIC["cases"][-1]], ids=lambda x: x["input"]["zone"]
)
def test_day_components_recover_the_same_complete_hash_verified_run(
    case, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "civil-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        case["input"], None, rest, tmp_path, capsys, budget=8192
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        assert_public_windows(original, case)
        assert (
            reconstruct(store, result_id, ROOT)
            == original["liuyao_evidence"]["conditional_analysis"]["timing_candidates"]
        )


def test_window_container_keeps_exact_component_count_and_durations(
    rest, tmp_path, capsys
):
    case = PUBLIC["cases"][-1]
    for output in all_surfaces(
        case["input"],
        [ROOT + ".windows"],
        rest,
        tmp_path,
        capsys,
    ):
        windows = output["liuyao_evidence"]["conditional_analysis"][
            "timing_candidates"
        ]["windows"]
        assert [
            x["civil_interval"]["duration_seconds"]
            for x in windows
            if "civil_interval" in x
        ] == [86400, 3600, 1800, 86400]


def test_array_leaf_projection_is_rejected_by_the_existing_contract(surface_calls):
    spec = SPECS["sixyao"]
    case = PUBLIC["cases"][-1]
    field = ROOT + ".windows.civil_interval.duration_seconds"
    response, protocol, code, local = surface_calls(
        spec,
        case["input"],
        params={"fields": field, "strict_fields": "true"},
        options={"fields": [field], "strict_fields": True},
        flags=["--fields", field, "--strict-fields", "true"],
    )
    assert response.status_code == 422 and code == 1 and protocol.is_error
    for body in [response.json(), local, protocol.structured_content]:
        assert body["issues"] == [{"path": field, "code": "non_object_projection_path"}]


@pytest.mark.parametrize(
    "day,base,changed,source,target,can_generate,benefit",
    [
        ("2002-01-29", "010011", "010010", 6, 5, True, None),
        ("2002-05-27", "011110", "011101", 5, 4, True, False),
        ("2000-02-26", "111111", "111110", 6, 5, False, False),
    ],
)
def test_source_generation_and_target_gate_are_equal_across_transports(
    day, base, changed, source, target, can_generate, benefit, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=target,
    )
    # Modern synthetic dates test transport. No ancient civil year inferred.
    field = "liuyao_evidence.conditional_analysis.generation_conditions"
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ]
        pair = next(
            g
            for g in detail["generations"]
            if (g["source_position"], g["target_position"]) == (source, target)
        )
        assert (
            pair.get("condition_match") is can_generate
            and pair.get("benefit_now") is benefit
        )
        assert pair["status"] and pair["target_status"]


def test_false_reception_leaf_projects_without_other_generation_fields(
    rest, tmp_path, capsys
):
    field = "liuyao_evidence.conditional_analysis.generation_conditions.focus.target_reception_condition"
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ] == {"focus": {"target_reception_condition": False}}


def test_same_run_generation_and_snapshot_keep_injury_and_target_void(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "generation-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-01-29",
        time="12:00:00",
        gua_code="010011",
        changed_code="010010",
        focus_line=5,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        gen = detail["generation_conditions"]
        source = gen["sources"][5]
        assert (
            source["condition_match"] is True
            and source["strength_supported_unopposed"] is False
        )
        assert any(
            a["location"] == "day" for a in source["retained_calendar_oppositions"]
        )
        assert gen["focus"]["target_reception_condition"] is None
        assert detail["void_conditions"]["focus"]["is_xunkong"] is True
        assert gen["scope"] in original["snapshot_text"]
        assert (
            "第6爻卯生第5爻巳：生源条件匹配；受生爻空破前提待审"
            in original["snapshot_text"]
        )
        path = "liuyao_evidence.conditional_analysis.generation_conditions"
        assert reconstruct(store, shaped["result_delivery"]["result_id"], path) == gen
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]


@pytest.mark.parametrize(
    "day,base,changed,position,growth,source",
    [
        ("2004-10-05", "000000", "000001", 6, True, True),
        ("2000-04-29", "000000", "000001", 6, True, None),
        ("2000-06-28", "000000", "000001", 6, None, None),
        ("2004-10-05", "011000", "010000", 3, True, False),
    ],
)
def test_growth_qualifications_and_source_effects(
    day, base, changed, position, growth, source, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=5,
    )
    for result in all_surfaces(
        payload,
        [
            root + ".growth_conditions",
            root + ".generation_conditions",
            root + ".role_effects",
        ],
        rest,
        tmp_path,
        capsys,
    ):
        detail = result["liuyao_evidence"]["conditional_analysis"]
        item = detail["growth_conditions"]["lines"][position - 1]
        assert item["position_match"] is True
        assert item.get("condition_match") is growth
        assert item["raw_day_element_relation"] == "克爻"
        assert (
            detail["generation_conditions"]["sources"][position - 1].get(
                "condition_match"
            )
            is source
        )
        role = next(
            r for r in detail["role_effects"]["lines"] if r["position"] == position
        )
        assert role["atom_values"]["day_growth_peak"] is True
        assert role["conditional_atom_values"].get("day_growth_peak") is growth


def test_replaced_calendar_control_false_leaf_is_preserved(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.growth_conditions.focus.day_control_in_calendar_oppositions"
    for result in all_surfaces(
        dict(
            date="2004-10-05",
            time="12:00:00",
            gua_code="000000",
            changed_code="000001",
            focus_line=6,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert result["liuyao_evidence"]["conditional_analysis"][
            "growth_conditions"
        ] == {"focus": {"day_control_in_calendar_oppositions": False}}


@pytest.mark.parametrize(
    "code,hidden_branch,flying_branch,applied",
    [("111001", "申", "辰", True), ("001101", "亥", "申", False)],
)
def test_hidden_and_flying_use_the_same_growth_qualification(
    code, hidden_branch, flying_branch, applied, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis.hidden_conditions"
    for result in all_surfaces(
        dict(
            date="2004-10-05",
            time="12:00:00",
            gua_code=code,
            focus_kind="hidden",
            focus_line=3,
        ),
        [root],
        rest,
        tmp_path,
        capsys,
    ):
        row = next(
            h
            for h in result["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 3
        )
        assert (row["branch"], row["flying_branch"]) == (hidden_branch, flying_branch)
        assert row["reception"]["calendar_growth_rule_applied"] is applied
        if applied:
            assert row["reception"]["condition_match"] is True
            assert row["reception"]["calendar_growth_source_url"].endswith("#page=97")
        else:
            assert "calendar_strikes_flying" not in row["reception"]["support_reasons"]
            assert row["reception"]["flying_growth_source_path"].endswith(
                "growth_conditions.lines.2"
            )


@pytest.mark.parametrize(
    "day,phrase",
    [
        ("2004-10-05", "已核月令独立生扶，巳日按长生条件"),
        ("2000-06-28", "不能据位置作得生"),
    ],
)
def test_same_run_growth_text_and_source_facts(
    day, phrase, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "growth-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        dict(
            date=day,
            time="12:00:00",
            gua_code="000000",
            changed_code="000001",
            focus_line=5,
        ),
        None,
        rest,
        tmp_path,
        capsys,
        budget=8192,
    ):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert phrase in original["snapshot_text"]
        row = original["liuyao_evidence"]["conditional_analysis"]["growth_conditions"][
            "lines"
        ][5]
        for path in row["month_support_fact_paths"]:
            value = original
            for part in path.split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert value["location"] == "month"


@pytest.mark.parametrize(
    "day,code,position,expected,flying",
    [
        ("2000-12-23", "011111", 2, True, True),
        ("2001-01-02", "011111", 2, True, None),
        ("2000-06-18", "001111", 1, False, False),
        ("2002-05-21", "000101", 1, None, False),
    ],
)
def test_hidden_gate_tristates_survive_strict_array_projection(
    day, code, position, expected, flying, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        gua_code=code,
        focus_kind="hidden",
        focus_line=position,
    )
    field = "liuyao_evidence.conditional_analysis.hidden_conditions"
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        rows = output["liuyao_evidence"]["conditional_analysis"]["hidden_conditions"]
        h = next(h for h in rows if h["position"] == position)
        assert h["reception"].get("condition_match") is expected
        assert h["reception"]["flying_generation"].get("condition_match") is flying
        assert h["reception"]["status"]


def test_hidden_model_false_leaf_does_not_require_siblings():
    from fatebridge.core.output_liuyao_hidden import HiddenReception

    assert HiddenReception.model_validate({"condition_match": False}).model_dump(
        exclude_none=True
    ) == {"condition_match": False}


def test_same_run_hidden_text_distinguishes_flying_void_from_its_support_alternative(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "hidden-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2001-01-02",
        time="12:00:00",
        gua_code="011111",
        focus_kind="hidden",
        focus_line=2,
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        h = next(
            h
            for h in original["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 2
        )
        assert h["reception"]["condition_match"] is True
        assert h["reception"]["flying_generation"]["condition_match"] is None
        assert (
            "所列受生引拔门槛匹配，仍未裁定最终出伏；飞生来源资格待审"
            in original["snapshot_text"]
        )
        assert (
            reconstruct(
                store,
                shaped["result_delivery"]["result_id"],
                h["reception"]["source_path"],
            )
            == h["reception"]
        )


@pytest.mark.parametrize("valid", [True, False])
def test_month_break_nested_projection_accepts_facts_and_rejects_typos(
    valid, surface_calls
):
    spec = SPECS["sixyao"]
    payload = dict(
        date="2004-10-03",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="000001",
        changed_code="000001",
        focus_line=3,
    )
    root = "liuyao_evidence.conditional_analysis.month_break_conditions.focus."
    fields = (
        [
            root + field
            for field in [
                "raw_month_break",
                "day_value_exception",
                "calendar_month_opposition",
            ]
        ]
        if valid
        else [root + "day_value_excpetion"]
    )
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
    )
    if not valid:
        assert http.status_code == 422 and code == 1 and protocol.is_error
        for body in [http.json(), cli, protocol.structured_content]:
            assert "liuyao_evidence" not in body
            assert body["issues"] == [
                {"path": fields[0], "code": "unknown_projection_path"}
            ]
        return
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        fact = body["liuyao_evidence"]["conditional_analysis"][
            "month_break_conditions"
        ]["focus"]
        assert fact == dict(
            raw_month_break=True,
            day_value_exception=True,
            calendar_month_opposition=False,
        )
        assert not body.get("projection_warnings")


@pytest.mark.parametrize(
    "day,base,changed,focus,kind,expected",
    [
        ("2002-05-27", "011110", "011101", 4, "visible", False),
        ("2006-09-28", "011110", "011101", 4, "visible", True),
        ("2002-05-21", "000101", "000001", 1, "hidden", None),
    ],
)
def test_route_qualification_survives_public_transports(
    day, base, changed, focus, kind, expected, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=focus,
        focus_kind=kind,
    )
    field = "liuyao_evidence.conditional_analysis.routing_conditions"
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"]["routing_conditions"]
        assert detail["focus"].get("condition_match") is expected
        assert detail["focus"]["status"]
        assert (
            detail["adjudication"]
            == "successive_generation_conditions_not_final_relief"
        )


def test_false_route_leaf_has_no_sibling_requirement(rest, tmp_path, capsys):
    field = (
        "liuyao_evidence.conditional_analysis.routing_conditions.focus.condition_match"
    )
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "routing_conditions"
        ] == {"focus": {"condition_match": False}}


def test_same_run_rootless_route_snapshot_retains_direct_control(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "routing-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        raw = next(
            c for c in detail["role_effects"]["chains"] if c["positions"] == [6, 5, 4]
        )
        assert (
            raw["status"] == "successive_generation_candidate"
            and raw["route_condition_match"] is False
        )
        edge = next(
            e
            for e in detail["interaction_edges"]
            if e["source_kind"] == "base"
            and (e["source_position"], e["target_position"]) == (6, 4)
        )
        assert (
            edge["relation"] == "克爻" and edge["qualified_routing_condition"] is False
        )
        assert "用神月破日克无独立根，不能据路径认定已受生" in original["snapshot_text"]
        assert detail["routing_conditions"]["scope"] in original["snapshot_text"]
        path = "liuyao_evidence.conditional_analysis.routing_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["routing_conditions"]
        )
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
