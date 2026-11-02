"""Selected observed UT1 series; this is not a complete EOP transformation."""

from typing import List, Optional

from fatebridge.core.output_base import PartialOutput


class C04UT1Evidence(PartialOutput):
    method_id: Optional[str] = None
    source_series: Optional[str] = None
    source_sha256: Optional[str] = None
    asset_sha256: Optional[str] = None
    source_url: Optional[str] = None
    mirror_url: Optional[str] = None
    mirror_commit: Optional[str] = None
    coverage_start_utc: Optional[str] = None
    coverage_end_utc: Optional[str] = None
    published_daily_records: Optional[int] = None
    query_julian_day_tt: Optional[float] = None
    query_julian_day_ut1: Optional[float] = None
    numerical_jd_resolution_seconds: Optional[float] = None
    source_mjd: Optional[List[int]] = None
    source_ut1_minus_utc_seconds: Optional[List[float]] = None
    source_formal_sigma_seconds: Optional[List[float]] = None
    interpolation_weight: Optional[float] = None
    instant_value_kind: Optional[str] = None
    ut1_minus_tai_seconds: Optional[float] = None
    delta_t_seconds: Optional[float] = None
    measured_ut1_series_applied: Optional[bool] = None
    polar_motion_applied: Optional[bool] = None
    celestial_pole_offsets_applied: Optional[bool] = None
    subdaily_tides_applied: Optional[bool] = None
    interpolation_error_bound_seconds: Optional[float] = None
    absolute_accuracy_certified: Optional[bool] = None
    epoch_scope: Optional[str] = None
    scope: Optional[str] = None
