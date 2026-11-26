"""UTC display labels without a dependency on chart or event schemas."""

from typing import Literal

from fatebridge.core.contracts.output_base import PartialOutput


class UTCDefinitionEvidence(PartialOutput):
    policy_id: str | None = None
    leap_table_expires_at: str | None = None


class WesternUTCRepresentation(PartialOutput):
    utc_label: str | None = None
    utc_is_leap_second: bool | None = None
    datetime_representable: bool | None = None
    label_status: str | None = None
    primary_axis: str | None = None
    scope: str | None = None
