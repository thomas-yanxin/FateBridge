"""Scoped presence, raw growth and qualified exclusion on public surfaces."""

import pytest

from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

pytest_plugins = ["tests.test_agentic_nested_outputs"]


@pytest.mark.parametrize(
    "day,code,changed,position,presence,growth",
    [
        ("2000-08-24", "000000", None, 2, True, False),
        ("2000-06-25", "000000", None, 2, False, True),
        ("2000-06-25", "000111", None, 2, None, None),
        ("2000-06-25", "000111", "000101", 2, True, False),
        ("2000-06-25", "000011", "000100", 5, True, False),
        ("2000-06-25", "000011", "000100", 2, False, True),
    ],
)
def test_scoped_triad_and_day_growth(
    day, code, changed, position, presence, growth, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    payload = dict(date=day, time="12:00:00", gua_code=code, focus_line=position)
    if changed:
        payload["changed_code"] = changed
    for output in all_surfaces(
        payload,
        [
            root + ".penalty_conditions",
            root + ".growth_conditions",
            root + ".classical_assessment",
        ],
        rest,
        tmp_path,
        capsys,
    ):
        result = output["liuyao_evidence"]["conditional_analysis"]
        penalty = result["penalty_conditions"]["focus"]
        assert penalty.get("condition_match") is presence
        assert penalty.get("day_yin_growth_allowed") is growth
        assert result["growth_conditions"]["focus"].get("condition_match") is growth
        assert result["growth_conditions"]["focus"]["position_match"] is True
        if presence is not False:
            assert penalty.get("effect_condition_match") is None
            assert (
                result["classical_assessment"]["focus"]["strength"].get("is_supported")
                is not True
            )


def test_false_penalty_leaf_and_unknown_effect_do_not_require_siblings(
    rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis.penalty_conditions.focus"
    for day, field, expected in [
        ("2000-06-25", "condition_match", False),
        ("2000-08-24", "effect_condition_match", None),
    ]:
        for output in all_surfaces(
            dict(date=day, time="12:00:00", gua_code="000000", focus_line=2),
            [root + "." + field],
            rest,
            tmp_path,
            capsys,
        ):
            assert output["liuyao_evidence"]["conditional_analysis"][
                "penalty_conditions"
            ] == {"focus": {field: expected}}


def test_hidden_same_day_generation_uses_its_own_penalty_context(
    rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    for output in all_surfaces(
        dict(
            date="2000-08-24",
            time="12:00:00",
            gua_code="100000",
            focus_kind="hidden",
            focus_line=2,
        ),
        [root + ".hidden_conditions"],
        rest,
        tmp_path,
        capsys,
    ):
        hidden = next(
            h
            for h in output["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 2
        )
        assert (
            hidden["branch"] == "巳"
            and hidden["reception"]["penalty"]["condition_match"] is True
        )
        condition = next(
            c
            for c in hidden["supporting_conditions"]
            if c["rule_id"] == "hidden_calendar_generates"
        )
        assert condition["matched"] is True and condition["qualified_matched"] is False
        assert "日辰生扶" not in hidden["reception"]["calendar_support_reasons"]
        assert hidden["reception"].get("condition_match") is None


def test_hidden_si_does_not_borrow_other_actual_changed_shen(rest, tmp_path, capsys):
    root = "liuyao_evidence.conditional_analysis.hidden_conditions"
    payload = dict(
        date="2000-06-25",
        time="12:00:00",
        gua_code="100001",
        changed_code="001001",
        focus_kind="hidden",
        focus_line=5,
    )
    for output in all_surfaces(payload, [root], rest, tmp_path, capsys):
        hidden = next(
            h
            for h in output["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 5
        )
        assert hidden["branch"] == "巳"
        penalty = hidden["reception"]["penalty"]
        assert penalty["condition_match"] is False
        assert penalty["day_yin_growth_allowed"] is True
        assert any(
            a["location"] == "changed" and a["position"] == 3 and a["branch"] == "申"
            for a in penalty["ignored_actors"]
        )


def test_line_only_pattern_attribution_and_explanation(rest, tmp_path, capsys):
    payload = dict(
        date="2000-07-06",
        time="12:00:00",
        gua_code="110111",
        changed_code="010101",
        focus_line=1,
    )
    for output in all_surfaces(payload, None, rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        assert detail["penalty_conditions"]["focus"]["condition_match"] is True
        harm = next(
            h
            for h in detail["classical_assessment"]["focus"]["strength"]["oppositions"]
            if "penalty_source_path" in h
        )
        assert harm["location"] == "pattern" and harm["branch"] == "巳"
        assert harm["pattern_actor_branches"] == ["寅", "申"]
        line = next(
            line
            for line in output["snapshot_text"].splitlines()
            if "第1爻巳克第5爻申" in line
        )
        # v21 same-edition priority supersedes the old implementation phrase:
        # the raw back-generation relation remains, its Yin credit is excluded.
        assert "三支总作用待审，本位回头生支持未确认" in line
        assert "本位回头生支持该条件" not in line
        assert (
            detail["back_generation_conditions"]["sources"][0]["raw_condition_match"]
            is True
        )
        assert (
            detail["back_generation_conditions"]["sources"][0]["condition_match"]
            is False
        )
        assert "原日月反制" not in line


def test_same_run_explanation_and_trace_follow_qualification(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "penalty-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(date="2000-08-24", time="12:00:00", gua_code="000000", focus_line=6)
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        assert detail["growth_conditions"]["lines"][1]["condition_match"] is False
        path = detail["penalty_conditions"]["lines"][1]["source_path"]
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["penalty_conditions"]["lines"][1]
        )
        assert (
            "寅日不按长生或同一日生扶计入；刑的总作用未裁定"
            in original["snapshot_text"]
        )
        trace = next(
            t
            for t in original["liuyao_evidence"]["rule_trace"]
            if t["rule_id"] == "si_yin_shen_scoped_growth_exclusion"
        )
        assert trace["sources"][0].endswith("#page=98")


@pytest.mark.parametrize(
    "changed,day,permission",
    [
        ("010101", "2000-07-06", False),
        ("010111", "2000-07-06", True),
        ("010110", "2000-06-25", None),
    ],
)
def test_own_yin_qualified_leaf_preserves_raw_gate(
    changed, day, permission, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    field = root + ".back_generation_conditions.focus.condition_match"
    for output in all_surfaces(
        dict(
            date=day,
            time="12:00:00",
            gua_code="110111",
            changed_code=changed,
            focus_line=1,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "back_generation_conditions"
        ] == {"focus": {"condition_match": permission}}


def test_hidden_yin_sources_obey_hidden_subject_priority(rest, tmp_path, capsys):
    root = "liuyao_evidence.conditional_analysis"
    for output in all_surfaces(
        dict(date="2000-03-03", time="12:00:00", gua_code="100000"),
        [root + ".hidden_conditions"],
        rest,
        tmp_path,
        capsys,
    ):
        h = next(
            h
            for h in output["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["branch"] == "巳" and h["position"] == 2
        )
        assert h["flying_branch"] == "寅"
        assert h["reception"]["penalty"]["condition_match"] is True
        assert h["reception"]["penalty"]["yin_generation_allowed"] is False
        assert h["reception"]["flying_generation"]["condition_match"] is False
        calendar = next(
            r
            for r in h["supporting_conditions"]
            if r["rule_id"] == "hidden_calendar_generates"
        )
        assert calendar["matched"] is True
        assert calendar["qualified_matched"] is False
