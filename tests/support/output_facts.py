"""Compare current calculation facts without execution receipts or rounding."""

import json


def canonical_json(payload: object) -> str:
    def facts(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: facts(item) for key, item in value.items() if key != "run_metadata"
            }
        if isinstance(value, (list, tuple)):
            return [facts(item) for item in value]
        return value

    return json.dumps(
        facts(payload), sort_keys=True, ensure_ascii=False, allow_nan=False
    )
