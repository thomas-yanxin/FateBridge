"""Historical second offsets and DST folds retain actual sampled instants."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo


@pytest.mark.parametrize(
    "zone", ["Asia/Kolkata", "Europe/Amsterdam", "Europe/Paris", "Africa/Monrovia"]
)
def test_minute_grid_does_not_reparse_historical_second_offsets(zone):
    person = PersonInfo(
        birth_year=1900,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=20,
        birth_second=59,
        birth_timezone=zone,
        use_true_solar_time=False,
    )
    result = analyze_birth_time_range(person, 1, analysis_moment=datetime(2026, 1, 1))
    assert result["sample_count"] == 3
    assert sum(r["sample_count"] for r in result["pillars_candidates"]) == 3
    assert datetime.fromisoformat(result["birth_at_range"]["start"]).second == 59
    assert datetime.fromisoformat(result["birth_at_range"]["end"]).second == 59
    assert "未证明采样间秒级无变化" in result["interpretation_scope"]


def test_sampling_preserves_both_fold_occurrences_without_defaulting_to_one(
    monkeypatch,
):
    import fatebridge.services.timing_uncertainty as module

    original = module.normalize_birth_time
    observed = []

    def observe(person, **kwargs):
        value = original(person, **kwargs)
        observed.append(
            localize_datetime(value.input_datetime, value.timezone).astimezone(
                timezone.utc
            )
        )
        return value

    monkeypatch.setattr(module, "normalize_birth_time", observe)
    person = PersonInfo(
        birth_year=2015,
        birth_month=11,
        birth_day=1,
        birth_hour=2,
        birth_minute=10,
        birth_second=59,
        birth_timezone="America/New_York",
        use_true_solar_time=False,
    )
    result = module.analyze_birth_time_range(
        person, 120, analysis_moment=datetime(2026, 1, 1)
    )
    samples = observed[1:]
    assert len(samples) == len(set(samples)) == result["sample_count"] == 241
    assert all(b - a == timedelta(minutes=1) for a, b in zip(samples, samples[1:]))
    assert result["birth_at_range"] == {
        "start": "2015-11-01T01:10:59-04:00",
        "end": "2015-11-01T04:10:59-05:00",
    }
