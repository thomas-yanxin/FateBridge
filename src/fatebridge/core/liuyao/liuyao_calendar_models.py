"""Report the available solar-model evidence for the selected sixyao month."""

from __future__ import annotations

from datetime import datetime, timezone

from fatebridge.core.almanac import BAZI_MONTH_START_TERMS, SOLAR_TERM_NAMES
from fatebridge.core.analytic_solar import MODEL_ID

SCOPE = (
    "只比较本次实际完成的交气路径；十二节才换月，中气不换月。"
    "两路时刻沿用原交气记录声明的民用时标约定。"
    "月令相关判断沿用本次采用月支，原生路径的另一月支仅说明模型选择敏感性。"
    "模型差值不是误差上界或准确率，也未修复原生Moshier、重排另一完整卦盘或证明预测有效。"
)


def month_model_comparison(
    moment: datetime,
    *,
    month_branch: str,
    boundary_models: tuple[str, str],
) -> dict[str, object] | None:
    """Report the missing alternate path for an explicitly analytic month."""
    if MODEL_ID not in boundary_models:
        return None
    else:
        pass
    return {
        "status": "not_compared_incomplete_native_probes",
        "calculation_month_branch": month_branch,
        "comparison_utc": moment.astimezone(timezone.utc).isoformat(),
        "compared_month_boundaries": 0,
        "missing_native_probes": [
            f"{year}:{name}"
            for year in range(moment.year - 1, moment.year + 2)
            for name in SOLAR_TERM_NAMES
            if name in BAZI_MONTH_START_TERMS
        ],
        "coverage_complete": False,
        "selected_models": sorted(set(boundary_models)),
        "native_models": [],
        "active_boundary_differences": [],
        "scope": SCOPE,
    }
