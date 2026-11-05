"""Disposable parent process for real public native-state isolation checks."""

import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "src"), str(root)]
from fatebridge.application.execution import execute_tool  # noqa: E402
from fatebridge.core.astro import native_execution, runtime  # noqa: E402
from fatebridge.services.tool_catalog import CATALOG  # noqa: E402
from fatebridge.validation.human_design import verify_human_design_reading  # noqa: E402


def main():
    year = int(sys.argv[1])
    directory = sys.argv[2]
    kind = sys.argv[3] if len(sys.argv) > 3 else "delta_t"
    assert not native_execution.in_native_worker()
    os.environ["SE_EPHE_PATH"] = directory
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    params = dict(
        birth_year=year,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="UTC",
    )
    spec = next(s for s in CATALOG if s.key == "human_design")
    first_run = execute_tool(spec, spec.request_model(**params))
    first = {k: v for k, v in first_run.items() if k != "run_metadata"}
    assert "activations" in first, first
    if kind == "delta_t":
        runtime.swe.set_delta_t_userdef(0.1)
    elif kind == "tidal_acceleration":
        runtime.swe.set_tid_acc(-999.0)
    elif kind == "stale_auxiliary":
        stale = Path(sys.argv[4])
        os.environ["SE_EPHE_PATH"] = str(stale)
        runtime.swe.set_ephe_path(str(stale))
        assert (
            abs(runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH) * 86400 - 400)
            < 1e-9
        )
        os.environ["SE_EPHE_PATH"] = directory
    else:
        raise AssertionError(kind)
    second_run = execute_tool(spec, spec.request_model(**params))
    second = {k: v for k, v in second_run.items() if k != "run_metadata"}
    assert "activations" in second, second
    assert first == second, (
        year,
        kind,
        [k for k in first if first[k] != second.get(k)],
    )
    if kind == "delta_t":
        assert runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH) == 0.1
    elif kind == "tidal_acceleration":
        assert runtime.swe.get_tid_acc() == -999.0
    else:
        assert (
            abs(runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH) * 86400 - 400)
            < 1e-9
        )
    for value in [first_run, second_run]:
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        assert value["native_execution_context"]["mechanism"] == "fresh_exec_process"
        assert (
            value["native_execution_context"]["lifetime"]
            == "one_outer_human_design_operation"
        )
    print(
        json.dumps(
            {
                "birth_input": params,
                "perturbation": kind,
                "complete_business_output_identical": True,
                "parent_setting_preserved": True,
                "full_readings_verified": True,
                "nominal_jd_tt": first["time_scales"]["personality"]["jd_tt"],
                "nominal_jd_ut1": first["time_scales"]["personality"]["jd_ut1"],
                "auxiliary_files_present": first["native_execution_context"][
                    "auxiliary_files_present"
                ],
                "scope": "Actual fresh production dispatch in two calls from a deliberately dirty disposable parent. No native reset or oracle tolerance substitution.",
            }
        )
    )


if __name__ == "__main__":
    main()
