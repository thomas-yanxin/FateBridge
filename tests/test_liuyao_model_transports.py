"""The model-choice-sensitive month is explicit on actual local protocols."""

import pytest

from tests.test_agentic_nested_outputs import rest
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_model_boundary import (
    CASES,
    ROOT,
    analytic_environment,
    assert_comparison,
)
from tests.test_liuyao_transports import assert_same_run_receipt


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
@pytest.mark.parametrize("project", [False, True])
def test_same_completed_path_comparison_in_rest_native_mcp_cli(
    case, project, rest, tmp_path, capsys
):
    for output in all_surfaces(
        case["input"], [ROOT] if project else None, rest, tmp_path, capsys
    ):
        assert_comparison(output, case)


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_false_and_true_month_change_leaf_survives_strict_projection(
    case, rest, tmp_path, capsys
):
    for output in all_surfaces(
        case["input"], [ROOT + ".month_changed"], rest, tmp_path, capsys
    ):
        value = output["liuyao_evidence"]["calendar_conventions"][
            "month_model_comparison"
        ]
        assert value == {"month_changed": case["month_changed"]}


@pytest.mark.parametrize("case", CASES[:2], ids=lambda x: x["id"])
def test_completed_probe_comparison_restores_the_same_hash_verified_run(
    case, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "model-choice-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        case["input"], None, rest, tmp_path, capsys, budget=8192
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        assert_comparison(original, case)
        assert (
            reconstruct(store, result_id, ROOT)
            == original["liuyao_evidence"]["calendar_conventions"][
                "month_model_comparison"
            ]
        )
