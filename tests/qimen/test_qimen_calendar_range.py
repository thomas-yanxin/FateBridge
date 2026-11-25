"""Full-service civil endpoints; only finite date facts have independent targets.

The targets were sealed before AFTER observations in R32's
qimen-priority-discovery/after-acceptance-preparation/
independent-day-policy-targets.json (SHA256 bb4d0e09e117661eacaabc9c6e8a9f12e5
cbdcbf4446d24111c24b071c2d37a7). They continue the frozen HKO 2026-01-01
乙亥, 01-20 甲午 and 01-31 乙巳 anchors over proleptic Gregorian day ordinals,
with the declared 23:00 day rollover. Fu-head/yuan use the selected 卷一
625938 conditions. This is not an ancient-calendar or solar-position oracle;
the nine retained traditional source obligations remain unresolved.

Execution needs the installed project/dev dependencies and bundled astronomy
assets. Auto selection may use native files or the bundled DE441 fallback;
the test does not pin a provider or assert astronomical/whole-board accuracy.
"""

import pytest

from fatebridge.services.metaphysics import calculate_qimen_analysis


@pytest.mark.parametrize(
    "parts,day_ganzhi,fu_tou,yuan,effective_date",
    [
        ((1, 7, 15, 12), "甲午", "甲午", "上元", "00010715"),
        ((1, 1, 1, 0), "己卯", "己卯", "上元", "00010101"),
        ((9999, 7, 15, 12), "戊辰", "甲子", "上元", "99990715"),
        ((9999, 12, 31, 23), "戊午", "甲寅", "中元", "+0100000101"),
    ],
    ids=["lower-end", "lower-jan1-midnight", "upper-end", "upper-dec31-latezi"],
)
def test_zhirun_service_accepts_civil_endpoints_with_independent_day_facts(
    monkeypatch: pytest.MonkeyPatch,
    parts: tuple[int, int, int, int],
    day_ganzhi: str,
    fu_tou: str,
    yuan: str,
    effective_date: str,
) -> None:
    # Isolate the existing default, rather than inherit a deliberately narrow
    # explicit model/JPL selection. Do not replace native paths or source data.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    year, month, day, hour = parts
    result = calculate_qimen_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=0,
        analysis_timezone="+00:00",
        use_true_solar_time=False,
        qimen_options={"ju_method": "zhirun"},
    )

    assert "error" not in result, result
    assert result["snapshot_text"]
    qimen = result["qimen"]
    assert qimen["ju_method"] == "zhirun"
    assert qimen["day_ganzhi"] == day_ganzhi
    assert qimen["fu_tou"] == fu_tou
    assert qimen["yuan"] == yuan
    assert qimen["ju_decision"]["effective_date"] == effective_date
    assert qimen["ju_decision"]["day_ganzhi"] == day_ganzhi
    assert qimen["ju_decision"]["yuan"] == yuan

    # Structural completion is not an oracle for the calculated ju/star/door.
    palaces = qimen["palaces"]
    assert len(palaces) == 9
    assert {palace["index"] for palace in palaces} == set(range(1, 10))
    assert all(
        {"name", "trigram", "heaven_stems", "earth_stems", "star", "door", "god"}
        <= palace.keys()
        for palace in palaces
    )
    assert qimen["zhifu"] and qimen["zhishi"]
    assert qimen["rulesets"] and qimen["rule_trace"]
    assert qimen["calendar_policy"]["day_boundary"] == "23:00"
    assert qimen["calendar_policy"]["hour_clock"] == "civil"
