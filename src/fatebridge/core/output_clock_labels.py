"""UTC display labels without a dependency on chart or event schemas."""

from typing import Optional

from fatebridge.core.output_base import PartialOutput


class WesternUTCRepresentation(PartialOutput):
    utc_label: Optional[str] = None
    utc_is_leap_second: Optional[bool] = None
    datetime_representable: Optional[bool] = None
    label_status: Optional[str] = None
    primary_axis: Optional[str] = None
    scope: Optional[str] = None
