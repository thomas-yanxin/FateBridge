"""Complete 6-fold Parashari Shadbala, Ishta/Kashta Phala, Raman Planetary War, and Bhava Bala."""

from __future__ import annotations

import math

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish.ephemeris import positions
from fatebridge.core.jyotish.shadbala import (
    BIMBA,
    PLANETS,
    REQUIRED_SHADBALA_RUPA,
    calculate_shadbala_bundle,
    compute_kala_and_cheshta,
    compute_sthana_bala,
)
from tests.fixtures.surface_payloads import astro_payload


def test_complete_shadbala_profiles_and_ishta_kashta_and_bhava_bala() -> None:
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(
        birth, ayanamsa="lahiri", node_mode="mean", cheshta_model="simon1994_j2000"
    )

    santh = calculate_shadbala_bundle(
        raw,
        birth.longitude,
        birth.latitude,
        saptavargaja_profile="santhanam_27",
        drekkana_profile="santhanam_27_6",
    )
    raman = calculate_shadbala_bundle(
        raw,
        birth.longitude,
        birth.latitude,
        saptavargaja_profile="raman_30",
        drekkana_profile="raman_36",
    )

    shad = santh["strengths"]["shadbala_assessment"]
    assert shad["status"] == "complete"
    assert len(shad["computed"]) == 6
    for p in PLANETS:
        assert math.isfinite(shad["total_virupa"][p])
        assert shad["total_rupa"][p] == pytest.approx(
            shad["total_virupa"][p] / 60.0, abs=1e-3
        )
        assert isinstance(shad["is_strong"][p], bool)
        assert shad["required_rupa"][p] == REQUIRED_SHADBALA_RUPA[p]
        ik = shad["ishta_kashta"][p]
        assert 0.0 <= ik["ishta_phala"] <= 60.0
        assert 0.0 <= ik["kashta_phala"] <= 60.0

    # Different profiles must yield distinct Saptavargaja / Drekkana values
    assert (
        santh["strengths"]["sthana_bala"]["summary"]["Sun"]["total_virupa"]
        != raman["strengths"]["sthana_bala"]["summary"]["Sun"]["total_virupa"]
        or santh["strengths"]["sthana_bala"]["summary"]["Venus"]["total_virupa"]
        != raman["strengths"]["sthana_bala"]["summary"]["Venus"]["total_virupa"]
    )

    # 12 houses Bhava Bala
    bhava = santh["strengths"]["bhava_bala"]
    assert len(bhava) == 12
    assert [row["house"] for row in bhava] == list(range(1, 13))
    for row in bhava:
        assert math.isfinite(row["total_virupa"])
        assert row["total_rupa"] == pytest.approx(row["total_virupa"] / 60.0, abs=1e-3)


def test_raman_76_77_planetary_war_exact_formula() -> None:
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    # Place Mars at 40.2° and Jupiter at 40.7° (0.5° separation -> lower longitude Mars wins)
    raw["longitudes"]["Mars"] = 40.2
    raw["longitudes"]["Jupiter"] = 40.7
    sthana = compute_sthana_bala(raw["longitudes"], raw["ascendant"])
    dig = {p: 30.0 for p in PLANETS}
    kala, _, _ = compute_kala_and_cheshta(
        raw,
        {"day_lord": "Sun", "hora_lord": "Sun", "tribhaga_lord": "Sun"},
        sthana,
        dig,
        birth.longitude,
    )
    war = kala["war_pairs"]
    assert len(war) == 1
    assert war[0]["winner"] == "Mars"
    assert war[0]["loser"] == "Jupiter"
    assert war[0]["separation_deg"] == pytest.approx(0.5, abs=1e-4)
    assert kala["components"]["yuddha_bala"]["Mars"] == pytest.approx(
        -kala["components"]["yuddha_bala"]["Jupiter"], abs=1e-4
    )
    assert kala["components"]["yuddha_bala"]["Mars"] > 0.0
    assert BIMBA["Jupiter"] == 190.4
