"""Bounded caches for immutable model contracts, never requests or results."""

from copy import deepcopy
from functools import lru_cache
from threading import RLock
from typing import Optional, Tuple, Type

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue

from fatebridge.utils.json_digest import digest

_LOCK = RLock()


class _SchemaRevision:
    """Keep the schema alive so a recycled object id cannot hit an old entry."""

    def __init__(self, schema: object) -> None:
        self.schema = schema

    def __hash__(self) -> int:
        return id(self.schema)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _SchemaRevision) and self.schema is other.schema


def _revision(model: Type[BaseModel]) -> _SchemaRevision:
    # Resolve deferred models before choosing the key. A forced model_rebuild
    # replaces the core schema, so it also invalidates the cached contract.
    if not model.__pydantic_complete__:
        model.model_rebuild()
    return _SchemaRevision(model.__pydantic_core_schema__)


@lru_cache(maxsize=256)
def _schema(model: Type[BaseModel], revision: _SchemaRevision) -> JsonSchemaValue:
    """Private snapshot; revision is part of the cache key, not wire data."""
    return model.model_json_schema()


def model_schema(model: Type[BaseModel]) -> JsonSchemaValue:
    """Return an independent public copy of the default validation schema.

    The lock prevents concurrent cold calls from generating the same schema
    multiple times. Neither transports nor callers can mutate the snapshot.
    """
    with _LOCK:
        return deepcopy(_schema(model, _revision(model)))


@lru_cache(maxsize=256)
def _fingerprint(
    request_model: Type[BaseModel],
    request_revision: _SchemaRevision,
    output_model: Optional[Type[BaseModel]],
    output_revision: Optional[_SchemaRevision],
    required_output_fields: Tuple[str, ...],
) -> str:
    output_schema = None
    if output_model is not None:
        assert output_revision is not None
        output_schema = _schema(output_model, output_revision)
    contract: dict[str, object] = {
        "input": _schema(request_model, request_revision),
        "output": output_schema,
    }
    if required_output_fields:
        contract["full_result_required_fields"] = list(required_output_fields)
    return digest(contract)


def contract_fingerprint(
    request_model: Type[BaseModel],
    output_model: Optional[Type[BaseModel]],
    required_output_fields: Tuple[str, ...] = (),
) -> str:
    """Hash model contracts and any complete-result requirements independently."""
    with _LOCK:
        return _fingerprint(
            request_model,
            _revision(request_model),
            output_model,
            _revision(output_model) if output_model else None,
            required_output_fields,
        )


def clear_contract_caches() -> None:
    """Explicitly invalidate contracts after changing model configuration/hooks.

    Registered models are otherwise immutable for the process lifetime. Tests
    and dynamic integrations must clear this cache when changing schema hooks
    or nested models without rebuilding their root models.
    """
    with _LOCK:
        _schema.cache_clear()
        _fingerprint.cache_clear()
