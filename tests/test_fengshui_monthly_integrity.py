"""A complete permutation and matching prose must not certify a wrong month."""

import asyncio
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.fengshui import monthly
from fatebridge.core.fengshui.models import MonthlyRequest
from fatebridge.core.fengshui.monthly_integrity import validate_monthly_layer
from fatebridge.services import fengshui as service
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.validation.fengshui_monthly import verify_monthly_reading
from tests.test_fengshui_surfaces import mcp_call, rest_client

ARCHIVE = Path(__file__).parent / "fixtures/fengshui_monthly_fault_v1"


def inputs():
    return {
        "effective_solar_year": 2026,
        "solar_month_number": 1,
        "timezone_name": "UTC",
    }


def corrupt(layer, fault):
    time = layer["time_context"]
    if fault == "rotation":
        stars = monthly.rule_data("annual_stars")
        layer["center_star_number"] = layer["center_star_number"] % 9 + 1
        for p in layer["palaces"].values():
            p["monthly_star_number"] = p["monthly_star_number"] % 9 + 1
            p["monthly_star"] = {
                k: stars[str(p["monthly_star_number"])][k] for k in ("name", "element")
            }
    elif fault == "swap":
        a, b = layer["palaces"]["N"], layer["palaces"]["S"]
        for field in ("monthly_star_number", "monthly_star"):
            a[field], b[field] = b[field], a[field]
    elif fault == "wrong_branch":
        layer["year_branch"] = "子"
    elif fault == "wrong_month":
        time["solar_month_number"] = 2
    elif fault == "wrong_year":
        time["effective_solar_year"] = 2027
    elif fault == "wrong_window":
        time["valid_from"] = time["valid_until"]
    elif fault == "boolean":
        layer["palaces"]["N"]["monthly_star_number"] = True
    elif fault == "wrong_star_identity":
        layer["palaces"]["N"]["monthly_star"]["element"] = "火"
    elif fault == "wrong_source_term":
        time["timing"]["start_resolution"]["term_name"] = "雨水"
    elif fault == "request_binding":
        time["timezone_name"] = "Asia/Shanghai"
    else:
        raise AssertionError(fault)
    return layer


def test_all_36_literal_centers_and_every_year_branch_remain_valid():
    source = json.loads(
        (ARCHIVE.parent / "fengshui_monthly_v1/reference.json").read_text()
    )
    for year in range(2020, 2032):
        branch = "子丑寅卯辰巳午未申酉戌亥"[(year - 4) % 12]
        column = next(
            g for g in source["printed_center_columns"] if branch in g["branches"]
        )
        for month, center in enumerate(column["centers"], 1):
            request = MonthlyRequest(
                effective_solar_year=year, solar_month_number=month
            )
            layer = monthly.monthly_stars(request)
            assert layer["center_star_number"] == center
            assert validate_monthly_layer(layer, request)["numeric_palaces"] == 9


@pytest.mark.parametrize(
    "fault",
    [
        "rotation",
        "swap",
        "wrong_branch",
        "wrong_month",
        "wrong_year",
        "wrong_window",
        "boolean",
        "wrong_star_identity",
        "wrong_source_term",
        "request_binding",
    ],
)
def test_wrong_values_cannot_hide_behind_a_complete_permutation(fault):
    request = MonthlyRequest(**inputs())
    layer = corrupt(monthly.monthly_stars(request), fault)
    with pytest.raises(FengshuiCalculationError) as caught:
        validate_monthly_layer(layer, request)
    assert caught.value.reason == "monthly_plate_inconsistent"


@pytest.mark.parametrize(
    "label,expected",
    [("correct", "verified_served_fixed_monthly_reading"), ("fault", "rejected")],
)
def test_actual_saved_old_results_use_their_original_receipts(label, expected):
    assert (
        hashlib.sha256((ARCHIVE / "hashes.json").read_bytes()).hexdigest()
        == "99a8c427fa4503e6e663154cd719aecd9d1ed2f80648c4b61240a88980b974a1"
    )
    for name, digest in json.loads((ARCHIVE / "hashes.json").read_text()).items():
        assert hashlib.sha256((ARCHIVE / name).read_bytes()).hexdigest() == digest
    result = json.loads(
        gzip.decompress((ARCHIVE / (label + "-result.json.gz")).read_bytes())
    )
    receipt = json.loads((ARCHIVE / (label + "-trusted-receipt.json")).read_text())
    checked = verify_monthly_reading(result, trusted_run_metadata=receipt)
    assert checked["status"] == expected
    assert checked["derived_monthly_numeric_consistency_verified"] is (
        label == "correct"
    )
    assert checked["calendar_accuracy_verified"] is False


def test_core_guard_uses_literal_month_table_not_the_producer_configuration(
    monkeypatch,
):
    original = monthly._bundle

    def wrong():
        value = deepcopy(original())
        value["year_groups"][0]["first_month_center"] = 9
        return value

    monkeypatch.setattr(monthly, "_bundle", wrong)
    with pytest.raises(FengshuiCalculationError):
        monthly.monthly_stars(MonthlyRequest(**inputs()))


@pytest.mark.parametrize("tool", ["monthly_stars", "assess"])
@pytest.mark.parametrize(
    "fault",
    ["rotation", "swap", "wrong_branch", "wrong_month", "wrong_year", "wrong_window"],
)
def test_service_seal_rejects_post_domain_faults_on_all_protocols(
    monkeypatch, tmp_path, capsys, tool, fault
):
    original = service.monthly_stars

    def wrong(request):
        value = corrupt(original(request), fault)
        value["position_reading"] = monthly.monthly_position_reading(value)
        return value

    monkeypatch.setattr(service, "monthly_stars", wrong)
    value = inputs()
    if tool == "assess":
        value = {"methods": ["monthly_stars"], "monthly": value}
    http = rest_client(monkeypatch).post(
        "/api/fengshui/" + tool,
        json=value,
        params={"fields": "status", "strict_fields": "true"},
    )
    protocol = asyncio.run(
        mcp_call(tool, {**value, "fields": ["status"], "strict_fields": True})
    )
    path = tmp_path / "request.json"
    path.write_text(json.dumps(value))
    code = run(
        [
            "fengshui_" + tool,
            "--request-file",
            str(path),
            "--fields",
            "status",
            "--strict-fields",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and protocol.is_error and code == 1
    for result in (http.json(), protocol.structured_content, cli):
        assert result["error_code"] == "fengshui_calculation_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {
                "path": "runtime.fengshui.monthly_stars",
                "code": "monthly_plate_inconsistent",
            }
        ]


def test_missing_month_does_not_receive_numeric_coverage():
    spec = next(s for s in CATALOG if s.key == "fengshui_monthly_stars")
    result = execute_tool(spec, spec.request_model.model_validate({}))
    checked = verify_monthly_reading(
        result, trusted_run_metadata=deepcopy(result["run_metadata"])
    )
    assert checked["status"] == "verified_served_fixed_monthly_reading"
    assert checked["derived_monthly_numeric_consistency_verified"] is False
