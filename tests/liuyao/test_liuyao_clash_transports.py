"""Clash facts, qualified effects and explanations survive public transports."""

from pathlib import Path

import pytest

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from tests.support.result_delivery import assert_same_run_receipt, reconstruct
from tests.support.transports import business
from tests.unit_test.fixtures.liuyao import all_surfaces


@pytest.mark.parametrize(
    "day,code,changed,focus,fill,broken,scatter",
    [
        ("2000-08-15", "110110", "110010", 4, False, False, False),
        ("2000-09-27", "010010", None, 3, True, False, None),
        ("2000-10-04", "000000", None, 4, False, None, None),
    ],
)
def test_clash_tristates_and_void_membership_across_transports(
    day: str,
    code: str,
    changed: str | None,
    focus: int,
    fill: bool,
    broken: bool | None,
    scatter: bool | None,
    rest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = "liuyao_evidence.conditional_analysis"
    payload = dict(
        date=day, time="12:00:00", zone="Asia/Shanghai", gua_code=code, focus_line=focus
    )
    if changed:
        payload["changed_code"] = changed
    else:
        pass
    for output in all_surfaces(
        payload,
        [f"{root}.clash_conditions", f"{root}.void_conditions", f"{root}.lines"],
        rest,
        tmp_path,
        capsys,
    ):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        clash = detail["clash_conditions"]["focus"]
        assert clash.get("day_void_fill_condition") is fill
        assert clash.get("day_break_condition") is broken
        assert clash.get("moving_scatter_condition") is scatter
        assert clash["day_break_status"] and clash["scatter_status"]
        if fill:
            assert detail["void_conditions"]["focus"]["is_xunkong"] is True
            assert detail["lines"][focus - 1]["activity_condition_match"] is True
        else:
            pass
        if broken is None:
            assert detail["lines"][focus - 1].get("activity_condition_match") is None
        else:
            pass


def test_false_clash_leaf_does_not_require_sibling_fields(
    rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    field = "liuyao_evidence.conditional_analysis.clash_conditions.focus.moving_scatter_condition"
    for output in all_surfaces(
        dict(
            date="2000-08-15",
            time="12:00:00",
            gua_code="110110",
            changed_code="110010",
            focus_line=4,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "clash_conditions"
        ] == {"focus": {"moving_scatter_condition": False}}


def test_clash_and_faithful_snapshot_restore_from_same_run(
    rest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    store = delivery.ResultStore(tmp_path / "clash-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2000-08-15",
        time="12:00:00",
        gua_code="110110",
        changed_code="110010",
        focus_line=2,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        water = next(r for r in detail["role_effects"]["lines"] if r["position"] == 4)
        assert water["atom_values"]["injured_relation"] is True
        assert water["conditional_atom_values"]["injured_relation"] is False
        path = "liuyao_evidence.conditional_analysis.clash_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["clash_conditions"]
        )
        assert detail["clash_conditions"]["scope"] in original["snapshot_text"]
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
