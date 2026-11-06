"""Projection-compatible base for public business output contracts."""

from typing import Annotated, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    ValidationInfo,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from fatebridge.core.public_output import is_integrity_field

T = TypeVar("T")
FullFact = Annotated[
    T, Field(json_schema_extra={"x-fatebridge-full-result": "non_null"})
]
PresentFact = Annotated[
    T, Field(json_schema_extra={"x-fatebridge-full-result": "present"})
]


class PartialOutput(BaseModel):
    """Validate present facts without inserting defaults or removing extensions.

    Object facts reachable by arbitrary field projection must be optional.
    Array items and receipts preserved whole may retain required facts, since
    projection cannot remove their siblings. Service results are validated but
    never serialized through these models.
    """

    model_config = ConfigDict(extra="allow", strict=True, defer_build=True)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler.resolve_ref_schema(handler(core_schema))
        properties = schema.get("properties", {})
        schema["properties"] = {
            name: value
            for name, value in properties.items()
            if not is_integrity_field(name)
        }
        if "required" in schema:
            schema["required"] = [
                name for name in schema["required"] if not is_integrity_field(name)
            ]
        return schema

    @model_validator(mode="after")
    def require_complete_facts(self, info: ValidationInfo) -> "PartialOutput":
        """Complete execution and projected public reads share one field contract."""
        if not info.context or not info.context.get("full_result"):
            return self
        for name, field in type(self).model_fields.items():
            metadata = field.json_schema_extra
            if not isinstance(metadata, dict):
                continue
            requirement = metadata.get("x-fatebridge-full-result")
            if requirement and (
                name not in self.model_fields_set
                or (requirement == "non_null" and getattr(self, name) is None)
            ):
                raise ValueError(f"完整结果缺少必要事实：{name}")
            identity_field = metadata.get("x-fatebridge-full-result-unique-by")
            value = getattr(self, name)
            if isinstance(identity_field, str) and value is not None:
                identities = [getattr(row, identity_field) for row in value]
                if len(identities) != len(set(identities)):
                    raise ValueError(f"完整结果集合身份重复：{name}")
                required = metadata.get("x-fatebridge-full-result-identities", [])
                if not isinstance(required, list) or any(
                    item not in identities for item in required
                ):
                    raise ValueError(f"完整结果缺少必要集合成员：{name}")
        return self
