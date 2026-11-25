"""Keep internal integrity bookkeeping out of public calculation results."""

import re
from functools import lru_cache

from pydantic import JsonValue

from fatebridge.utils.json_values import same_value

_INTEGRITY_FIELD = re.compile(
    r"(?:^|_)(?:sha\d*|md5|hash(?:es)?|digest(?:s)?|fingerprint(?:s)?)(?:_|$)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1024)
def is_integrity_field(name: str) -> bool:
    return (
        name in {"first_record_identities", "pixel_firsts"}
        or _INTEGRITY_FIELD.search(name) is not None
    )


def public_value(value: JsonValue) -> JsonValue:
    """Copy structured facts while retaining source names, versions and locations.

    Internal validators consume the original result first. This boundary applies
    equally to full responses, projections and stored result bodies; it never
    changes source files or treats missing integrity fields as validation success.
    """
    if isinstance(value, dict):
        return public_payload(value)
    if isinstance(value, (list, tuple)):
        return [public_value(item) for item in value]
    return value


def public_payload(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        name: public_value(value)
        for name, value in payload.items()
        if not is_integrity_field(name)
    }


def same_public_value(left: object, right: object) -> bool:
    return same_value(left, right, exclude_field=is_integrity_field)
