"""Hidden reception qualification and same-run text on REST, CLI and MCP."""

import pytest

from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt


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
    from tests.test_result_delivery import reconstruct

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
