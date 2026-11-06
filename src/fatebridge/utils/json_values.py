"""Exact JSON fact comparison, including boolean and numeric types."""

from collections.abc import Callable


def same_value(
    left: object,
    right: object,
    *,
    exclude_field: Callable[[str], bool] | None = None,
) -> bool:
    if type(left) is not type(right):
        return False
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
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            same_value(a, b, exclude_field=exclude_field) for a, b in zip(left, right)
        )
    return bool(left == right)
