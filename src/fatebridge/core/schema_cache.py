"""Bounded caches for immutable model contracts, never requests or results."""

from copy import deepcopy
from functools import lru_cache
from threading import RLock

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

SCHEMA_CACHE_LOCK = RLock()


class _SchemaRevision:
    """Keep the schema alive so a recycled object id cannot hit an old entry."""

    def __init__(self, schema: CoreSchema) -> None:
        self.schema: CoreSchema = schema

    def __hash__(self) -> int:
        return id(self.schema)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _SchemaRevision) and self.schema is other.schema


def _revision(model: type[BaseModel]) -> _SchemaRevision:
    # Resolve deferred models before choosing the key. A forced model_rebuild
    # replaces the core schema, so it also invalidates the cached contract.
    if not model.__pydantic_complete__:
        model.model_rebuild()
    return _SchemaRevision(model.__pydantic_core_schema__)


@lru_cache(maxsize=256)
def _schema(model: type[BaseModel], revision: _SchemaRevision) -> JsonSchemaValue:
    """Private snapshot; revision is part of the cache key, not wire data."""
    return model.model_json_schema()


def model_schema(model: type[BaseModel]) -> JsonSchemaValue:
    """Return an independent public copy of the default validation schema.

    The lock prevents concurrent cold calls from generating the same schema
    multiple times. Neither transports nor callers can mutate the snapshot.
    """
    with SCHEMA_CACHE_LOCK:
        return deepcopy(_schema(model, _revision(model)))


def clear_contract_caches() -> None:
    """Explicitly invalidate contracts after changing model configuration/hooks.

    Registered models are otherwise immutable for the process lifetime. Tests
    and dynamic integrations must clear this cache when changing schema hooks
    or nested models without rebuilding their root models.
    """
    with SCHEMA_CACHE_LOCK:
        _schema.cache_clear()
