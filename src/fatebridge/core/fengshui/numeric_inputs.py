"""JSON numerical and calendar facts keep their declared types before any transport can coerce them."""

import math
import re
import types
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from numbers import Integral, Real
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BeforeValidator
from pydantic_core import PydanticCustomError

from fatebridge.core.requests.base import _DeferredModel


def _unwrap(annotation: Any) -> Any:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _kind(annotation: Any) -> str | None:
    annotation = _unwrap(annotation)
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        if args and all(type(v) in (int, float) for v in args):
            return "number" if any(type(v) is float for v in args) else "integer"
    if origin in (Union, types.UnionType):
        kinds = [_kind(arg) for arg in args if arg is not type(None)]
        if kinds and all(kinds):
            return "number" if "number" in kinds else "integer"
    return None


def _temporal_kind(annotation: Any) -> str | None:
    annotation = _unwrap(annotation)
    if annotation is datetime:
        return "datetime"
    if annotation is date:
        return "date"
    if get_origin(annotation) in (Union, types.UnionType):
        kinds = [
            _temporal_kind(arg) for arg in get_args(annotation) if arg is not type(None)
        ]
        if kinds and len(set(kinds)) == 1:
            return kinds[0]
    return None


def _contains_number(annotation: Any) -> bool:
    annotation = _unwrap(annotation)
    if _kind(annotation) is not None or _temporal_kind(annotation) is not None:
        return True
    return any(
        _contains_number(arg) for arg in get_args(annotation) if arg is not Ellipsis
    )


def _allows_bool(annotation: Any, value: bool) -> bool:
    annotation = _unwrap(annotation)
    if annotation is bool:
        return True
    if get_origin(annotation) is Literal:
        return any(type(arg) is bool and arg is value for arg in get_args(annotation))
    if get_origin(annotation) in (Union, types.UnionType):
        return any(_allows_bool(arg, value) for arg in get_args(annotation))
    return False


def _finite(value: Any) -> bool:
    if isinstance(value, Integral) or isinstance(value, Fraction):
        return True
    if isinstance(value, Decimal):
        return value.is_finite()
    return math.isfinite(value)


def _normalize(annotation: Any, value: Any) -> Any:
    annotation = _unwrap(annotation)
    if value is None:
        return value
    temporal = _temporal_kind(annotation)
    if temporal == "date":
        if (isinstance(value, date) and not isinstance(value, datetime)) or (
            isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        ):
            return value
        raise PydanticCustomError(
            "date_type",
            "Input should be an ISO calendar date (YYYY-MM-DD) or a date object",
        )
    if temporal == "datetime":
        if isinstance(value, datetime) or (
            isinstance(value, str)
            and re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}", value)
        ):
            return value
        raise PydanticCustomError(
            "datetime_type",
            "Input should be an explicit ISO date and clock or a datetime object; numeric timestamps are not accepted",
        )
    kind = _kind(annotation)
    if isinstance(value, bool) and _contains_number(annotation):
        if _allows_bool(annotation, value):
            return value
        raise PydanticCustomError(
            "int_type" if kind == "integer" else "float_type",
            (
                "Input should be a valid integer"
                if kind == "integer"
                else "Input should be a valid number"
            ),
        )
    if kind is not None:
        if not isinstance(value, (Real, Decimal)):
            raise PydanticCustomError(
                "int_type" if kind == "integer" else "float_type",
                (
                    "Input should be a valid integer"
                    if kind == "integer"
                    else "Input should be a valid number"
                ),
            )
        if not _finite(value):
            raise PydanticCustomError(
                "finite_number", "Input should be a finite number"
            )
        # JSON Schema integers include integral JSON numbers such as 8.0.
        # Exact equality is required; never round a fractional observation.
        if kind == "integer":
            integer = int(math.trunc(value))
            if value == integer:
                return integer
        return value
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        choices = [arg for arg in args if arg is not type(None)]
        if len(choices) == 1:
            return _normalize(choices[0], value)
    if origin is list and isinstance(value, list) and args:
        return [_normalize(args[0], item) for item in value]
    if origin is dict and isinstance(value, dict) and len(args) == 2:
        return {key: _normalize(args[1], item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class _NumericGuard:
    annotation: Any

    def __call__(self, value: Any) -> Any:
        return _normalize(self.annotation, value)


class FengshuiInput(_DeferredModel):
    """Attach the same fact-type precondition to nested and flattened fields."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        changed = False
        for info in cls.model_fields.values():
            if _contains_number(info.annotation):
                info.metadata = [
                    item
                    for item in info.metadata
                    if not (
                        isinstance(item, BeforeValidator)
                        and isinstance(item.func, _NumericGuard)
                    )
                ] + [BeforeValidator(_NumericGuard(info.annotation))]
                changed = True
        if changed and cls.__pydantic_complete__:
            cls.model_rebuild(force=True)
