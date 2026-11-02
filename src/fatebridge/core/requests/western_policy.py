"""Shared explicit source-admission control for Western requests."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from fatebridge.core.requests.base import _DeferredModel


class WesternEphemerisRequest(_DeferredModel):
    ephemeris_policy: Literal["auto", "require_data_files"] = Field(
        default="auto",
        json_schema_extra={"x-fatebridge-western-data-policy": True},
        description="auto retains and reports actual available models. require_data_files rejects analytical/orbital fallback for observed physical coordinates throughout the request, including clocks and samples; checks data contexts and endpoint hashes. Native rise/set query/result epochs are probed, but internal solver reads are not fully observable. Analytical points, fictitious elements, reference zeros and Earth rotation are separate; this is not an astronomical-accuracy or prediction certificate.",
    )

    def uses_western_ephemeris_policy(self) -> bool:
        return True


def uses_western_policy(request: BaseModel) -> bool:
    return (
        isinstance(request, WesternEphemerisRequest)
        and request.uses_western_ephemeris_policy()
    )


def supports_western_policy_model(model: type[BaseModel]) -> bool:
    field = model.model_fields.get("ephemeris_policy")
    extra = field.json_schema_extra if field is not None else None
    return (
        isinstance(extra, dict)
        and extra.get("x-fatebridge-western-data-policy") is True
    )


def service_inputs(request: BaseModel) -> dict[str, Any]:
    return request.model_dump(
        exclude={"ephemeris_policy"} if uses_western_policy(request) else set()
    )
