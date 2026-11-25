"""Selected observed UT1 series; this is not a complete EOP transformation."""

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput


class C04UT1Evidence(PartialOutput):
    method_id: str | None = None
    source_series: str | None = None
    source_sha256: str | None = None
    asset_sha256: str | None = None
    orientation_asset_sha256: str | None = None
    tidal_asset_sha256: str | None = None
    tidal_model_id: str | None = None
    source_url: str | None = None
    mirror_url: str | None = None
    mirror_commit: str | None = None
    coverage_start_utc: str | None = None
    coverage_end_utc: str | None = None
    published_daily_records: int | None = None
    query_julian_day_tt: float | None = None
    query_julian_day_ut1: float | None = None
    numerical_jd_resolution_seconds: float | None = None
    source_mjd: list[int] | None = None
    source_ut1_minus_utc_seconds: list[float] | None = None
    source_formal_sigma_seconds: list[float] | None = None
    interpolation_weights: list[float] | None = None
    interpolation_axis: str | None = None
    instant_value_kind: str | None = None
    ut1_minus_tai_seconds: float | None = None
    base_ut1_minus_tai_seconds: float | None = Field(
        default=None,
        description=(
            "Restored daily UT1-TAI base, including query Z62 after four-point "
            "interpolation of zonal-regularized source values. Add only the "
            "subdaily field; the zonal field must not be added again."
        ),
    )
    zonal_ut1_seconds: float | None = None
    subdaily_ut1_seconds: float | None = None
    delta_t_seconds: float | None = None
    solver_residual_seconds: float | None = Field(
        default=None,
        description=(
            "Absolute forward pair-equation residual at the retained TT/UT1, "
            "in seconds. Numerical solver diagnostic, not a physical error bound."
        ),
    )
    solver_tolerance_seconds: float | None = Field(
        default=None,
        description="Forward solve convergence threshold in seconds.",
    )
    solver_iterations: int | None = Field(
        default=None,
        description="Iterations in the forward solve used to check source agreement.",
    )
    measured_ut1_series_applied: bool | None = None
    polar_motion_applied: bool | None = None
    celestial_pole_offsets_applied: bool | None = None
    subdaily_tides_applied: bool | None = None
    interpolation_error_bound_seconds: float | None = None
    absolute_accuracy_certified: bool | None = None
    epoch_scope: str | None = None
    scope: str | None = None
