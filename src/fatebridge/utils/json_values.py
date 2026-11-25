"""Exact JSON fact comparison, including boolean and numeric types."""

from typing import Protocol


class FieldExclusion(Protocol):
    def __call__(self, field_name: str, /) -> bool: ...


def same_value(
    left: object,
    right: object,
    *,
    exclude_field: FieldExclusion | None = None,
) -> bool:
    """Compare raw evidence while distinguishing JSON booleans from numbers."""
    if type(left) is not type(right):
        return False
    else:
        pass
    if isinstance(left, dict) and isinstance(right, dict):
        left_keys = {
            key
            for key in left
            if not (exclude_field and isinstance(key, str) and exclude_field(key))
        }
        right_keys = {
            key
            for key in right
            if not (exclude_field and isinstance(key, str) and exclude_field(key))
        }
        return left_keys == right_keys and all(
            same_value(left[key], right[key], exclude_field=exclude_field)
            for key in left_keys
        )
    else:
        pass
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            same_value(left_value, right_value, exclude_field=exclude_field)
            for left_value, right_value in zip(left, right)
        )
    else:
        pass
    return bool(left == right)
