"""Split day components and literal snapshot data survive all three surfaces."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.test_liuyao_civil_windows import PUBLIC, ROOT, assert_public_windows
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt


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
    from tests.test_result_delivery import reconstruct

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


def test_array_leaf_projection_is_rejected_by_the_existing_contract(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    case = PUBLIC["cases"][-1]
    field = ROOT + ".windows.civil_interval.duration_seconds"
    response = rest.post(
        spec.rest_path,
        json=case["input"],
        params={"fields": field, "strict_fields": "true"},
    )
    code, local = call_cli(
        spec,
        case["input"],
        tmp_path,
        capsys,
        flags=["--fields", field, "--strict-fields", "true"],
    )
    protocol = asyncio.run(
        native(spec, case["input"], fields=[field], strict_fields=True)
    )
    assert response.status_code == 422 and code == 1 and protocol.is_error
    for body in [response.json(), local, protocol.structured_content]:
        assert body["issues"] == [{"path": field, "code": "non_object_projection_path"}]
