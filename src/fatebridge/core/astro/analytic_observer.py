"""One coherent DE441 receiver and target source with fixed-reception optics.

All source states share the original TDB grid and fixed mean-J2000 bias.
One local-TT-delay light cone supplies every physical ray, including the Moon.
The declared finite-source bending and Lorentz aberration act on that same
ray before display rotation and TT longitude differentiation.
"""

from __future__ import annotations

from fractions import Fraction

from fatebridge.core.astro.aberration_math import (
    LIGHT_SPEED_AU_PER_DAY,
    aberration_beta_jvp,
    aberration_position,
    aberration_position_jvp,
    dot,
)
from fatebridge.core.astro.cartesian import CartesianMotion, CartesianState
from fatebridge.core.astro.de441_source import SourceKinematics, mean_j2000_state
from fatebridge.core.astro.light_cone import solve_light_cone
from fatebridge.core.astro.solar_deflection import finite_source_solar_deflection

LIGHT_TIME_METHOD = (
    "fixed_reception_adjacent_TT_delay_DE441_two_part_source_light_cone_v3"
)
ABERRATION_METHOD = "Lorentz_observer_DE441_barycentric_analytic_TDB_velocity_v2"


class AnalyticObserver:
    def __init__(self) -> None:
        self._sources: dict[tuple[str, float | Fraction, float], SourceKinematics] = {}

    def _source_state(
        self, body: str, tt_days: float | Fraction, offset_days: float = 0.0
    ) -> SourceKinematics:
        key = (body, tt_days, offset_days)
        if key not in self._sources:
            self._sources[key] = mean_j2000_state(body, tt_days, offset_days)
        else:
            pass
        return self._sources[key]

    def apparent_state(
        self, planet: str, tt_days: float | Fraction, offset_days: float = 0.0
    ) -> CartesianMotion:
        """The same position map and its complete local TT derivative.

        Differentiate te - t + |target(te)-Earth(t)|/c = 0 implicitly.
        Each source velocity first receives its own TDB/TT ratio; the
        observer beta remains native TDB velocity and its TT derivative
        uses the source acceleration. No neighboring reception is sampled.
        """
        earth = self._source_state("Earth", tt_days, offset_days)
        sun = self._source_state("Sun", tt_days, offset_days)

        def sample(delay: float) -> tuple[tuple[float, ...], SourceKinematics]:
            state = self._source_state(planet, tt_days, offset_days + delay)
            return state.position, state

        solution = solve_light_cone(0.0, earth.position, sample)
        x, y, z = solution.upper.coordinates
        target = (x, y, z)
        x, y, z = (a - b for a, b in zip(target, earth.position))
        ray = (x, y, z)
        distance = solution.upper.distance
        direction = tuple(value / distance for value in ray)
        earth_tt = tuple(v * earth.tdb_rate for v in earth.velocity)
        emitted = solution.upper.payload
        target_tt = tuple(v * emitted.tdb_rate for v in emitted.velocity)
        emission_rate = (1 + dot(direction, earth_tt) / LIGHT_SPEED_AU_PER_DAY) / (
            1 + dot(direction, target_tt) / LIGHT_SPEED_AU_PER_DAY
        )
        vx, vy, vz = (a * emission_rate - b for a, b in zip(target_tt, earth_tt))
        motion = CartesianMotion(ray, (vx, vy, vz))
        if planet not in {"Sun", "Moon"}:
            emitting_sun = self._source_state(
                "Sun", tt_days, offset_days + solution.upper.epoch
            )
            tx, ty, tz = (v * emission_rate for v in target_tt)
            ex, ey, ez = earth_tt
            sx, sy, sz = (v * sun.tdb_rate for v in sun.velocity)
            ux, uy, uz = (
                v * emitting_sun.tdb_rate * emission_rate for v in emitting_sun.velocity
            )
            motion = finite_source_solar_deflection(
                CartesianState(ray, (vx, vy, vz)),
                CartesianState(earth.position, (ex, ey, ez)),
                CartesianState(sun.position, (sx, sy, sz)),
                CartesianState(target, (tx, ty, tz)),
                CartesianState(emitting_sun.position, (ux, uy, uz)),
            )
        else:
            pass
        beta = tuple(v / LIGHT_SPEED_AU_PER_DAY for v in earth.velocity)
        if motion.velocity is None:
            x, y, z = aberration_position(motion.position, beta)
            return CartesianMotion((x, y, z), None)
        else:
            pass
        apparent, position_change = aberration_position_jvp(
            motion.position, motion.velocity, beta
        )
        _, beta_change = aberration_beta_jvp(
            motion.position,
            beta,
            tuple(
                v * earth.tdb_rate / LIGHT_SPEED_AU_PER_DAY for v in earth.acceleration
            ),
        )
        x, y, z = apparent
        vx, vy, vz = (a + b for a, b in zip(position_change, beta_change))
        return CartesianMotion((x, y, z), (vx, vy, vz))

    def apparent_position(
        self, planet: str, tt_days: float | Fraction, offset_days: float = 0.0
    ) -> tuple[float, float, float]:
        """Compute only apparent position, skipping unused velocity/acceleration derivatives."""
        if planet not in {"Sun", "Moon"}:
            return self.apparent_state(planet, tt_days, offset_days).position
        else:
            pass
        earth = mean_j2000_state("Earth", tt_days, offset_days, derivatives=1)

        def sample(delay: float) -> tuple[tuple[float, ...], None]:
            state = mean_j2000_state(
                planet, tt_days, offset_days + delay, derivatives=0
            )
            return state.position, None

        solution = solve_light_cone(0.0, earth.position, sample)
        tx, ty, tz = solution.upper.coordinates
        ex, ey, ez = earth.position
        ray = (tx - ex, ty - ey, tz - ez)
        beta = (
            earth.velocity[0] / LIGHT_SPEED_AU_PER_DAY,
            earth.velocity[1] / LIGHT_SPEED_AU_PER_DAY,
            earth.velocity[2] / LIGHT_SPEED_AU_PER_DAY,
        )
        return aberration_position(ray, beta)
