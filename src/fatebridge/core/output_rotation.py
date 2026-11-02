"""Shared projected contract for the actually selected Earth-rotation policy."""

from typing import Dict, Optional

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_ut1 import C04UT1Evidence


class LongtermPhaseAlignment(PartialOutput):
    method: Optional[str] = None
    boundary_tt_jd: Optional[float] = None
    native_longterm_variation_retained: Optional[bool] = None
    absolute_accuracy_certified: Optional[bool] = None
    derivative_continuity_certified: Optional[bool] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    attribution: Optional[str] = None


class EarthRotationPolicy(PartialOutput):
    tt_argument_policy: Optional[str] = None
    ut1_reference: Optional[C04UT1Evidence] = None
    policy_id: Optional[str] = None
    sidereal_time_model: Optional[str] = None
    implementation: Optional[str] = None
    model_epoch_jd_tt: Optional[float] = None
    model_epoch_jd_ut1: Optional[float] = None
    modern_adoption_window_tt: Optional[Dict[str, float]] = None
    native_iers_interval_ut1: Optional[Dict[str, float]] = None
    selection_basis: Optional[str] = None
    longterm_phase_alignment: Optional[LongtermPhaseAlignment] = None
    nutation_model: Optional[str] = None
    other_astronomical_models: Optional[str] = None
    geographic_longitude_policy: Optional[str] = None
    scope: Optional[str] = None
    measured_eop_applied: Optional[bool] = None
    precision_scope: Optional[str] = None
    source_url: Optional[str] = None
