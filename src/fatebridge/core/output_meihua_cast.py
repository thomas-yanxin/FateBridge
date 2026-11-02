"""Public, projection-compatible output of explicit Mei Hua casting."""

from typing import Dict, Optional

from pydantic import JsonValue

from .output_chinese import Meihua
from .response_models import ProjectedOutput, RunMetadata


class MeihuaCastOutput(ProjectedOutput):
    run_metadata: Optional[RunMetadata] = None
    analysis_type: Optional[str] = None
    input_normalized: Optional[Dict[str, JsonValue]] = None
    meihua: Optional[Meihua] = None
    interpretation: Optional[Dict[str, JsonValue]] = None
    summary: Optional[str] = None
