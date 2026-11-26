"""Share outputs for the fixed Jin Kou branch-break and natal cases."""

from functools import lru_cache
from typing import Literal

from pydantic import JsonValue

from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.support.transports import SPECS
from tests.unit_test.fixtures.ren_protocol import REN_PROTOCOL_PAYLOAD

JINKOU_SPEC = SPECS["jinkou"]
assert JINKOU_SPEC.rest_path is not None
BRANCH_BREAKS_PAYLOAD: dict[str, JsonValue] = {
    **REST_POST_CASES[JINKOU_SPEC.rest_path](),
    "birth_year_ganzhi": "甲子",
    "year_fate_age": 43,
    "gender": "男",
}


@lru_cache(maxsize=1)
def branch_breaks_output() -> dict[str, JsonValue]:
    request = JINKOU_SPEC.request_model.model_validate(BRANCH_BREAKS_PAYLOAD)
    calculate, arguments, keywords = JINKOU_SPEC.bind(request)
    return calculate(*arguments, **keywords)


def jinkou_course(
    output: dict[str, JsonValue], role: Literal["primary", "natal_course", "year_fate"]
) -> dict[str, JsonValue]:
    primary_course = output["jinkou"]
    assert isinstance(primary_course, dict)
    if role == "primary":
        return primary_course
    else:
        nested_course = primary_course[role]
        assert isinstance(nested_course, dict)
        course = nested_course["course"]
        assert isinstance(course, dict)
        return course


def natal_branch_output(natal_branch: str | None = "酉") -> dict[str, JsonValue]:
    request = JINKOU_SPEC.request_model.model_validate(
        dict(REN_PROTOCOL_PAYLOAD, di_fen="酉", natal_branch=natal_branch)
    )
    calculate, arguments, keywords = JINKOU_SPEC.bind(request)
    return calculate(*arguments, **keywords)
