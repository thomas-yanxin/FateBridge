"""Assemble a line-reference packet from a complete verified original result."""

from __future__ import annotations

import hashlib
from copy import deepcopy

from fatebridge.core import human_design_knowledge as knowledge
from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.core.human_design_line_reading import METHOD, _compose
from fatebridge.core.human_design_references import coherent_human_design_references
from fatebridge.validation.human_design import verify_human_design_reading


class LineReadingInputError(ValueError):
    def __init__(self, verification: dict) -> None:
        self.verification = verification
        super().__init__("A complete verified original Human Design result is required")


def build_human_design_line_packet(source_result: dict) -> dict:
    source_result = deepcopy(source_result)
    with coherent_human_design_references():
        verification = verify_human_design_reading(source_result)
        if verification["status"] != "verified_fixed_template_reading":
            raise LineReadingInputError(verification)
        data, snapshot = knowledge._catalogue()
        provenance = knowledge._provenance(data, snapshot)
        keys = dict.fromkeys(
            f"{r['gate']}.{r['line']}"
            for r in source_result["depth_evidence"]["line_fixings"]
        )
        references = {
            key: knowledge.read_reference(category="lines", key=key) for key in keys
        }
        if any(r["provenance"] != provenance for r in references.values()):
            raise ValueError("Line references do not share one source snapshot")
        identity = source_result["run_metadata"]
        packet = {
            "method_id": METHOD,
            "packet_version": 1,
            "source_identity": {
                "original_result_sha256": hashlib.sha256(
                    _canonical(source_result)
                ).hexdigest(),
                "run_id": identity["run_id"],
            },
            "original_result": deepcopy(source_result),
            "source_calculation_verification": verification,
            "line_reading": _compose(source_result, references),
            "line_reference_provenance": provenance,
            "complete384_line_semantics_accepted": False,
            "arbitrary_model_free_text_accepted": False,
            "publisher_master_authenticated": False,
            "real_world_prediction_validated": False,
        }
        knowledge._check_end(snapshot)
        return packet
