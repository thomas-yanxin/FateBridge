"""Public facts and schemas exclude internal integrity bookkeeping."""

from copy import deepcopy

import pytest
from pydantic import Field

from fatebridge.application.projection import project_fields
from fatebridge.core.output_base import PartialOutput
from fatebridge.core.public_output import public_payload
from fatebridge.utils.errors import ParameterError


def test_public_boundary_preserves_facts_and_does_not_mutate_internal_evidence():
    internal = {
        "source": {
            "title": "原典",
            "author": "作者",
            "url": "https://example.org/source",
            "page": 7,
            "version": "1.0",
            "source_sha256": "a" * 64,
        },
        "facts": [
            {"value": -0.0, "source_fingerprint": "internal"},
            {"status": "partial", "unknown": None, "input_hash": "internal"},
        ],
        "numbers": [0, False, 1.2345678901234567],
        "digest": "internal",
        "run_metadata": {"run_id": "current-run", "environment_sha256": "b" * 64},
    }
    before = deepcopy(internal)
    actual = public_payload(internal)
    assert actual == {
        "source": {
            "title": "原典",
            "author": "作者",
            "url": "https://example.org/source",
            "page": 7,
            "version": "1.0",
        },
        "facts": [{"value": -0.0}, {"status": "partial", "unknown": None}],
        "numbers": [0, False, 1.2345678901234567],
        "run_metadata": {"run_id": "current-run"},
    }
    assert internal == before
    assert str(actual["facts"][0]["value"]) == "-0.0"
    with pytest.raises(ParameterError):
        project_fields(actual, ["source.source_sha256"], strict_fields=True)


def test_output_schema_hides_internal_fields_without_weakening_internal_validation():
    class Source(PartialOutput):
        filename: str
        sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    class Output(PartialOutput):
        sources: list[Source]

    schema = Output.model_json_schema()
    source = schema["$defs"]["Source"]
    assert set(source["properties"]) == {"filename"}
    assert source["required"] == ["filename"]
    assert Source.model_fields["sha256"].is_required()
    with pytest.raises(ValueError):
        Output.model_validate(
            {"sources": [{"filename": "source.pdf", "sha256": "bad"}]}
        )
