"""Public, projection-compatible output of explicit Mei Hua casting."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_chinese_calendar import Meihua
from fatebridge.core.contracts.output_projection import ProjectedOutput
from fatebridge.core.receipt_models import RunMetadata


class MeihuaCastOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    analysis_type: str | None = None
    analysis_context: dict[str, JsonValue] | None = None
    meihua: Meihua | None = None
    interpretation: dict[str, JsonValue] | None = None
    summary: str | None = None
