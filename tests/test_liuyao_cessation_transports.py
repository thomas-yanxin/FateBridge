"""Earth/Si role qualification and retained raw facts across public surfaces."""

import pytest

from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

pytest_plugins = ["tests.test_agentic_nested_outputs"]


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
    from tests.test_result_delivery import reconstruct

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
