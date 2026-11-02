"""Independent reference clock and source-table propagation; no FateBridge imports.

The pre1960 adapter deliberately shares Swiss' declared UT1/Delta-T model.
SOFA/IERS civil coefficients are independently frozen primary-source inputs.
Future UTC labels use the explicit constant-last-offset assumption.
"""

from __future__ import annotations

import bisect
from datetime import date, datetime, timedelta, timezone
from typing import Any

NAMES = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
MODERN = [
    ("1972-01-01", 10),
    ("1972-07-01", 11),
    ("1973-01-01", 12),
    ("1974-01-01", 13),
    ("1975-01-01", 14),
    ("1976-01-01", 15),
    ("1977-01-01", 16),
    ("1978-01-01", 17),
    ("1979-01-01", 18),
    ("1980-01-01", 19),
    ("1981-07-01", 20),
    ("1982-07-01", 21),
    ("1983-07-01", 22),
    ("1985-07-01", 23),
    ("1988-01-01", 24),
    ("1990-01-01", 25),
    ("1991-01-01", 26),
    ("1992-07-01", 27),
    ("1993-07-01", 28),
    ("1994-07-01", 29),
    ("1996-01-01", 30),
    ("1997-07-01", 31),
    ("1999-01-01", 32),
    ("2006-01-01", 33),
    ("2009-01-01", 34),
    ("2012-07-01", 35),
    ("2015-07-01", 36),
    ("2017-01-01", 37),
]


def midnight(label: str) -> datetime:
    return datetime.fromisoformat(label).replace(tzinfo=timezone.utc)


def civil_jd(moment: datetime) -> float:
    return (
        2451544.5
        + (moment - datetime(2000, 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400
    )


class ReferenceClock:
    def __init__(self, coefficients: list[dict[str, Any]], swe: Any) -> None:
        self.coefficients = coefficients
        self.swe = swe

    def forward(self, moment: datetime) -> tuple[float, str]:
        if moment.year < 1960:
            t = self.swe.utc_to_jd(
                moment.year,
                moment.month,
                moment.day,
                moment.hour,
                moment.minute,
                moment.second + moment.microsecond / 1e6,
                self.swe.GREG_CAL,
            )
            return float(t[0]), "declared_Swiss_historical_UT1"
        jd = civil_jd(moment)
        if moment.year < 1972:
            row = next(
                r
                for r in reversed(self.coefficients)
                if moment.date().isoformat() >= r["effective_date"]
            )
            offset = (
                row["offset_seconds"]
                + (jd - 2400000.5 - row["reference_mjd"]) * row["rate_seconds_per_day"]
            )
            return jd + (offset + 32.184) / 86400, "SOFA_IERS_affine_UTC"
        offset = next(v for label, v in reversed(MODERN) if moment >= midnight(label))
        return jd + (offset + 32.184) / 86400, "IERS_modern_constant_last_offset"

    def inverse(self, tt: float) -> datetime:
        for label, offset in reversed(MODERN):
            if tt >= civil_jd(midnight(label)) + (offset + 32.184) / 86400:
                return datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(
                    days=tt - (offset + 32.184) / 86400 - 2451544.5
                )
        first = midnight(self.coefficients[0]["effective_date"])
        first_tt = self.forward(first)[0]
        if tt >= first_tt:
            candidates = []
            for i, row in enumerate(self.coefficients):
                start = civil_jd(midnight(row["effective_date"]))
                stop = civil_jd(
                    midnight(
                        self.coefficients[i + 1]["effective_date"]
                        if i + 1 < len(self.coefficients)
                        else "1972-01-01"
                    )
                )
                rate = row["rate_seconds_per_day"]
                # Solve t = u + [offset+(u-MJDref)*rate+32.184]/86400.
                u = (
                    tt
                    - (
                        row["offset_seconds"]
                        + 32.184
                        - (2400000.5 + row["reference_mjd"]) * rate
                    )
                    / 86400
                ) / (1 + rate / 86400)
                if start <= u < stop:
                    candidates.append(
                        datetime(2000, 1, 1, tzinfo=timezone.utc)
                        + timedelta(days=u - 2451544.5)
                    )
            if len(candidates) != 1:
                raise ValueError("Unrepresentable historical UTC adjustment")
            return candidates[0]
        y, m, d, h, minute, second = self.swe.jdet_to_utc(tt, self.swe.GREG_CAL)
        return datetime(y, m, d, h, minute, tzinfo=timezone.utc) + timedelta(
            seconds=second
        )


def source_expectation(
    roots: list[dict[str, Any]],
    times: list[float],
    moment: datetime,
    tt: float,
    protocol: dict[str, Any],
    calendar: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    idx = bisect.bisect_right(times, tt) - 1
    if idx < 0 or idx + 1 >= len(roots):
        raise ValueError("Reference guard roots must cover every probe")
    current, following = roots[idx], roots[idx + 1]
    spring = next(v for v in reversed(roots[: idx + 1]) if v["index"] == 2)
    jie = next(
        v
        for v in reversed(roots[: idx + 1])
        if NAMES[v["index"]] in calendar["month_starts"]
    )
    year = spring["year"]
    year_pair = STEMS[(year - 1984) % 10] + BRANCHES[(year - 1984) % 12]
    month = calendar["month_starts"][NAMES[jie["index"]]]
    month_stems = next(
        v for k, v in calendar["month_stems"].items() if year_pair[0] in k
    )
    month_pair = month_stems["寅卯辰巳午未申酉戌亥子丑".index(month)] + month
    cycle = (
        calendar["day_cycle"]["jdn_anchor"]
        + (moment.date() - date(2000, 1, 1)).days
        + int(moment.hour >= 23)
        + calendar["day_cycle"]["cycle_offset"]
    ) % 60
    day = STEMS[cycle % 10] + BRANCHES[cycle % 12]
    hour = BRANCHES[((moment.hour + 1) // 2) % 12]
    hour_stems = next(v for k, v in calendar["hour_stems"].items() if day[0] in k)
    ground = protocol["di_fen"]
    human = hour_stems[BRANCHES.index(ground)]
    guiren = next(v["day"] for v in rules["guiren"] if v["stem"] == day[0])
    distance = (BRANCHES.index(ground) - BRANCHES.index(guiren)) % 12
    god = protocol["reference_maps"]["gui_sequence"][
        (-distance if guiren in "巳午未申酉戌" else distance) % 12
    ]
    god_branch = rules["inherent"][god][1]
    general = protocol["reference_maps"]["general_by_last_term"][
        NAMES[current["index"]]
    ]
    general_branch = BRANCHES[
        (BRANCHES.index(general) + BRANCHES.index(ground) - BRANCHES.index(hour)) % 12
    ]
    positions = [human, god_branch, general_branch, ground]
    maps = protocol["reference_maps"]
    elements = [maps["stem_elements"][human]] + [
        maps["branch_elements"][v] for v in positions[1:]
    ]
    powers = [rules["power"][maps["branch_elements"][month]][v] for v in elements]
    mask = ("阳" if STEMS.index(human) % 2 == 0 else "阴") + "".join(
        "阳" if BRANCHES.index(v) % 2 == 0 else "阴" for v in positions[1:]
    )
    use = next(v["use"] for v in rules["polarity_use"] if v["mask"] == mask)
    return dict(
        current_term=NAMES[current["index"]],
        next_term=NAMES[following["index"]],
        year=year_pair,
        month=month_pair,
        day=day,
        hour=hour_stems[BRANCHES.index(hour)] + hour,
        month_general=general,
        positions=positions,
        seasonal_powers=powers,
        polarity_use=use,
    )
