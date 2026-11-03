"""Offline geocentric orbital approximation, independent of chart assembly.

Paul Schlyter's low-precision formulae: https://stjarnhimlen.se/comp/ppcomp.html
The Pluto fit is described for about 1800–2100, not the whole public year range.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from fatebridge.core.astro.geometry import (
    _cos_deg,
    _deg_to_rad,
    _rad_to_deg,
    _sin_deg,
    normalize_angle,
)
from fatebridge.core.astro.reference import PLANET_ORBITAL_ELEMENTS


def _solve_kepler(mean_anomaly_deg: float, eccentricity: float) -> float:
    mean_anomaly_rad = _deg_to_rad(mean_anomaly_deg)
    estimate = mean_anomaly_rad
    for _ in range(8):
        numerator = estimate - eccentricity * math.sin(estimate) - mean_anomaly_rad
        denominator = 1 - eccentricity * math.cos(estimate)
        estimate -= numerator / denominator
    return estimate


def _planet_heliocentric_coords(
    planet: str, day_number: float
) -> Tuple[float, float, float]:
    (
        ascending_node,
        inclination,
        perihelion,
        semi_major_axis,
        eccentricity,
        mean_anomaly,
    ) = PLANET_ORBITAL_ELEMENTS[planet](day_number)
    eccentric_anomaly = _solve_kepler(normalize_angle(mean_anomaly), eccentricity)
    xv = semi_major_axis * (math.cos(eccentric_anomaly) - eccentricity)
    yv = semi_major_axis * (
        math.sqrt(1 - eccentricity * eccentricity) * math.sin(eccentric_anomaly)
    )
    true_anomaly = _rad_to_deg(math.atan2(yv, xv))
    radius = math.sqrt(xv * xv + yv * yv)
    argument = normalize_angle(true_anomaly + perihelion)
    xh = radius * (
        _cos_deg(ascending_node) * _cos_deg(argument)
        - _sin_deg(ascending_node) * _sin_deg(argument) * _cos_deg(inclination)
    )
    yh = radius * (
        _sin_deg(ascending_node) * _cos_deg(argument)
        + _cos_deg(ascending_node) * _sin_deg(argument) * _cos_deg(inclination)
    )
    zh = radius * (_sin_deg(argument) * _sin_deg(inclination))
    return xh, yh, zh


def _sun_state(day_number: float) -> Dict[str, float]:
    perihelion = 282.9404 + 4.70935e-5 * day_number
    eccentricity = 0.016709 - 1.151e-9 * day_number
    mean_anomaly = normalize_angle(356.047 + 0.9856002585 * day_number)
    eccentric_anomaly = _solve_kepler(mean_anomaly, eccentricity)
    xv = math.cos(eccentric_anomaly) - eccentricity
    yv = math.sqrt(1 - eccentricity * eccentricity) * math.sin(eccentric_anomaly)
    true_anomaly = _rad_to_deg(math.atan2(yv, xv))
    radius = math.sqrt(xv * xv + yv * yv)
    longitude = normalize_angle(true_anomaly + perihelion)
    return {
        "longitude": longitude,
        "radius": radius,
        "mean_anomaly": mean_anomaly,
        "x": radius * _cos_deg(longitude),
        "y": radius * _sin_deg(longitude),
    }


def _moon_state(day_number: float, sun_state: Dict[str, float]) -> Dict[str, float]:
    ascending_node = 125.1228 - 0.0529538083 * day_number
    inclination = 5.1454
    perihelion = 318.0634 + 0.1643573223 * day_number
    semi_major_axis = 60.2666
    eccentricity = 0.0549
    mean_anomaly = normalize_angle(115.3654 + 13.0649929509 * day_number)
    eccentric_anomaly = _solve_kepler(mean_anomaly, eccentricity)
    xv = semi_major_axis * (math.cos(eccentric_anomaly) - eccentricity)
    yv = semi_major_axis * (
        math.sqrt(1 - eccentricity * eccentricity) * math.sin(eccentric_anomaly)
    )
    true_anomaly = _rad_to_deg(math.atan2(yv, xv))
    radius = math.sqrt(xv * xv + yv * yv)
    argument = normalize_angle(true_anomaly + perihelion)
    xh = radius * (
        _cos_deg(ascending_node) * _cos_deg(argument)
        - _sin_deg(ascending_node) * _sin_deg(argument) * _cos_deg(inclination)
    )
    yh = radius * (
        _sin_deg(ascending_node) * _cos_deg(argument)
        + _cos_deg(ascending_node) * _sin_deg(argument) * _cos_deg(inclination)
    )
    zh = radius * (_sin_deg(argument) * _sin_deg(inclination))

    longitude = normalize_angle(_rad_to_deg(math.atan2(yh, xh)))
    latitude = _rad_to_deg(math.atan2(zh, math.sqrt(xh * xh + yh * yh)))
    mean_longitude = normalize_angle(ascending_node + perihelion + mean_anomaly)
    elongation = normalize_angle(mean_longitude - sun_state["longitude"])
    argument_of_latitude = normalize_angle(mean_longitude - ascending_node)
    sun_mean_anomaly = sun_state["mean_anomaly"]

    longitude += (
        -1.274 * _sin_deg(mean_anomaly - 2 * elongation)
        + 0.658 * _sin_deg(2 * elongation)
        - 0.186 * _sin_deg(sun_mean_anomaly)
        - 0.059 * _sin_deg(2 * mean_anomaly - 2 * elongation)
        - 0.057 * _sin_deg(mean_anomaly - 2 * elongation + sun_mean_anomaly)
        + 0.053 * _sin_deg(mean_anomaly + 2 * elongation)
        + 0.046 * _sin_deg(2 * elongation - sun_mean_anomaly)
        + 0.041 * _sin_deg(mean_anomaly - sun_mean_anomaly)
        - 0.035 * _sin_deg(elongation)
        - 0.031 * _sin_deg(mean_anomaly + sun_mean_anomaly)
        - 0.015 * _sin_deg(2 * argument_of_latitude - 2 * elongation)
        + 0.011 * _sin_deg(mean_anomaly - 4 * elongation)
    )
    latitude += (
        -0.173 * _sin_deg(argument_of_latitude - 2 * elongation)
        - 0.055 * _sin_deg(mean_anomaly - argument_of_latitude - 2 * elongation)
        - 0.046 * _sin_deg(mean_anomaly + argument_of_latitude - 2 * elongation)
        + 0.033 * _sin_deg(argument_of_latitude + 2 * elongation)
        + 0.017 * _sin_deg(2 * mean_anomaly + argument_of_latitude)
    )
    return {"longitude": normalize_angle(longitude), "latitude": latitude}


def _pluto_heliocentric_coords(day_number: float) -> Tuple[float, float, float]:
    s = 50.03 + 0.033459652 * day_number
    p = 238.95 + 0.003968789 * day_number
    longitude = (
        238.9508
        + 0.00400703 * day_number
        - 19.799 * _sin_deg(p)
        + 19.848 * _cos_deg(p)
        + 0.897 * _sin_deg(2 * p)
        - 4.956 * _cos_deg(2 * p)
        + 0.61 * _sin_deg(3 * p)
        + 1.211 * _cos_deg(3 * p)
        - 0.341 * _sin_deg(4 * p)
        - 0.19 * _cos_deg(4 * p)
        + 0.128 * _sin_deg(5 * p)
        - 0.034 * _cos_deg(5 * p)
        - 0.038 * _sin_deg(6 * p)
        + 0.031 * _cos_deg(6 * p)
        + 0.02 * _sin_deg(s - p)
        - 0.01 * _cos_deg(s - p)
    )
    latitude = (
        -3.9082
        - 5.453 * _sin_deg(p)
        - 14.975 * _cos_deg(p)
        + 3.527 * _sin_deg(2 * p)
        + 1.673 * _cos_deg(2 * p)
        - 1.051 * _sin_deg(3 * p)
        + 0.328 * _cos_deg(3 * p)
        + 0.179 * _sin_deg(4 * p)
        - 0.292 * _cos_deg(4 * p)
        + 0.019 * _sin_deg(5 * p)
        + 0.1 * _cos_deg(5 * p)
        - 0.031 * _sin_deg(6 * p)
        - 0.026 * _cos_deg(6 * p)
        + 0.011 * _cos_deg(s - p)
    )
    radius = (
        40.72
        + 6.68 * _sin_deg(p)
        + 6.90 * _cos_deg(p)
        - 1.18 * _sin_deg(2 * p)
        - 0.03 * _cos_deg(2 * p)
        + 0.15 * _sin_deg(3 * p)
        - 0.14 * _cos_deg(3 * p)
    )
    return (
        radius * _cos_deg(longitude) * _cos_deg(latitude),
        radius * _sin_deg(longitude) * _cos_deg(latitude),
        radius * _sin_deg(latitude),
    )


def _planet_state(
    planet: str, day_number: float, sun_state: Dict[str, float]
) -> Dict[str, float]:
    if planet == "Sun":
        return {"longitude": sun_state["longitude"], "latitude": 0.0}
    if planet == "Moon":
        return _moon_state(day_number, sun_state)
    if planet == "North Node":
        return {
            "longitude": normalize_angle(125.1228 - 0.0529538083 * day_number),
            "latitude": 0.0,
        }

    # Pluto's Fourier fit is heliocentric too; apply the same Earth-centred
    # translation as the Keplerian planets instead of returning the raw fit.
    xh, yh, zh = (
        _pluto_heliocentric_coords(day_number)
        if planet == "Pluto"
        else _planet_heliocentric_coords(planet, day_number)
    )
    xg = xh + sun_state["x"]
    yg = yh + sun_state["y"]
    zg = zh
    longitude = normalize_angle(_rad_to_deg(math.atan2(yg, xg)))
    latitude = _rad_to_deg(math.atan2(zg, math.sqrt(xg * xg + yg * yg)))
    return {"longitude": longitude, "latitude": latitude}
