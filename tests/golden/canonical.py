"""Golden-master 输出规范化：把工具响应压成确定性的 JSON 文本。

规范化做三件事，让「同一份计算」永远得到逐字节相同的快照：
1. 剔除易变字段（如 ``run_metadata.generated_at`` 这种每次都变的时间戳）；
2. 浮点统一 round 到固定精度，吸收跨 Python 版本的末位浮点噪声；
3. 键排序后序列化。
"""

from __future__ import annotations

import json
import math
from typing import Any

#: 每次重算都会变、与命理计算无关的字段，冻结前一律剔除。
#: ``run_metadata`` 每次调用都会注入新的 ``generated_at`` 时间戳与
#: ``run_id`` / ``trace_id``（均为 uuid4），不剔除会让基线每次都不同。
VOLATILE_KEYS = frozenset({"generated_at", "run_id", "trace_id"})

# Execution receipts have separate contract/replay tests. Their build hashes,
# duration and real call clock are not calculation facts; schema/input/business
# hashes also depend on unsanitized payloads. Restrict removal to run_metadata,
# retaining business provenance, warning lists and the pre-existing engine keys.
EXECUTION_RECEIPT_KEYS = frozenset(
    {
        "metadata_schema_version",
        "package_version",
        "contract_sha256",
        "input_sha256",
        "business_output_sha256",
        "duration_ms",
        "effective_time",
        "determinism",
        "runtime",
        "provenance",
        "replay",
        "warnings",
        "parent_run_id",
    }
)

#: 浮点保留精度。远高于任何命理意义阈值，仅用于吸收末位浮点噪声。
FLOAT_PRECISION = 8


def _scrub(value: Any, *, execution_metadata: bool = False) -> Any:
    """递归剔除易变字段并规整浮点（tuple 视同 list 处理）。"""
    if isinstance(value, dict):
        return {
            k: _scrub(v, execution_metadata=k == "run_metadata")
            for k, v in value.items()
            if k not in VOLATILE_KEYS
            and not (execution_metadata and k in EXECUTION_RECEIPT_KEYS)
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(item) for item in value]
    if isinstance(value, float):
        rounded = round(value, FLOAT_PRECISION)
        # A snapshot must not manufacture 30°/360° or change a sign-boundary
        # side. Preserve the input double where fixed decimal rounding would
        # cross a 30-degree partition. Non-finite values retain JSON's rejection.
        if math.isfinite(value) and value // 30.0 != rounded // 30.0:
            return value
        return rounded
    return value


def canonical_json(payload: Any) -> str:
    """把响应对象压成确定性 JSON 文本（剔易变字段、定浮点精度、排序键）。

    ``allow_nan=False``：若计算意外产出 NaN/Inf 就当场报错，既避免写出非法
    JSON，也能让真正的数值异常暴露出来，而不是被悄悄冻进基线。
    """
    return json.dumps(
        _scrub(payload),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
