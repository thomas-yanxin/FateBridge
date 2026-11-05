import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
from fatebridge.core.astro import runtime  # noqa: E402
from fatebridge.core.requests.human_design import HumanDesignRequest  # noqa: E402

params = json.loads(sys.argv[1])
kind = sys.argv[2]


def status():
    try:
        r = HumanDesignRequest(**params)
        return {"accepted": True, "normalized_request": r.model_dump()}
    except ValueError as error:
        return {
            "accepted": False,
            "error_class": type(error).__name__,
            "error": str(error),
        }


clean = status()
if kind == "delta_t":
    runtime.swe.set_delta_t_userdef(0.1)
    before = runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH)
else:
    runtime.swe.set_tid_acc(-999.0)
    before = runtime.swe.get_tid_acc()
dirty = status()
after = (
    runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH)
    if kind == "delta_t"
    else runtime.swe.get_tid_acc()
)
assert clean["accepted"] == dirty["accepted"], (clean, dirty)
assert before == after, (before, after)
if clean["accepted"]:
    assert clean["normalized_request"] == dirty["normalized_request"]
print(
    json.dumps(
        {
            "input": params,
            "perturbation": kind,
            "clean": clean,
            "dirty": dirty,
            "parent_setting_before": before,
            "parent_setting_after": after,
            "parent_setting_preserved": before == after,
        }
    )
)
