"""Compatibility tool declarations."""

from __future__ import annotations

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_pair,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import BatchInputPolicy, ToolSpec

calculate_compatibility_analysis = service_ref(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)
calculate_sukuyo_compatibility = service_ref(
    "fatebridge.services.divination", "calculate_sukuyo_compatibility"
)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_compatibility",
        bind=bind_pair(
            calculate_compatibility_analysis,
            extra_fields=("person1_zi_hour_policy", "person2_zi_hour_policy"),
        ),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.compatibility", "TwoPersonCompatibilityRequest"
        ),
        required_output_fields=(
            "natal_contexts",
            "cross_chart_relations",
            "directional_ten_gods",
        ),
        summary="双人八字合婚与关系分析：四柱、喜用互补、年命纳音、鸳鸯合、跨盘干支、双向十神及神煞互照。",
        operation_label_zh="双人八字合盘",
        family="compatibility",
        rest_path="/api/bazi/compatibility",
        cpu_bound=True,
        default_omit=(
            "natal_contexts.*.calendar_context",
            "natal_contexts.*.day_master",
            "cross_chart_relations.directional_punishments",
            "directional_ten_gods",
        ),
        batch_policy=BatchInputPolicy(
            subject_mode="pair",
            pair_prefixes=("person1_", "person2_"),
            pair_style="birth_fields",
        ),
    ),
    ToolSpec(
        name="sukuyo_compatibility",
        bind=bind_kwargs(calculate_sukuyo_compatibility),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.compatibility", "SukuyoCompatibilityRequest"
        ),
        required_output_fields=("person1", "person2", "status"),
        summary="宿曜双人相性：农历月日定二十七宿，T1299三九法双向关系；闰月保留候选。",
        operation_label_zh="宿曜合盘",
        family="compatibility",
        rest_path="/api/compatibility/sukuyo",
        default_omit=(
            "person1.calendar",
            "person2.calendar",
            "person1.palace_reference",
            "person2.palace_reference",
        ),
        batch_policy=BatchInputPolicy(
            subject_mode="pair",
            pair_prefixes=("person1_", "person2_"),
            pair_style="date_zone",
        ),
    ),
]
