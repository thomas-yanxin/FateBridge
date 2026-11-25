"""Independent integer-ratio reference for declared Vimshottari clocks."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction

LORD_YEARS = (
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
)
YEAR_DAYS = {
    "savana_360": Fraction(360),
    "tropical_365_2425": Fraction("365.2425"),
    "sidereal_365_25636": Fraction("365.25636"),
}
DAY_MICROSECONDS = 86_400_000_000


def quantize_microseconds(value: Fraction) -> int:
    """Round an exact edge using integer quotient and parity, including negatives."""
    quotient, remainder = divmod(value.numerator, value.denominator)
    comparison = 2 * remainder - value.denominator
    return quotient + int(comparison > 0 or (comparison == 0 and quotient % 2 == 1))


@dataclass(frozen=True)
class ReferencePeriod:
    lord_chain: tuple[str, ...]
    start_microseconds: Fraction
    end_microseconds: Fraction

    def clocks(self, birth: datetime) -> tuple[str, str]:
        start = birth + timedelta(
            microseconds=quantize_microseconds(self.start_microseconds)
        )
        end = birth + timedelta(
            microseconds=quantize_microseconds(self.end_microseconds)
        )
        return start.isoformat(), end.isoformat()


def reference_periods(
    moon_degrees: Fraction,
    target_microseconds: int,
    year_basis: str,
    depth: int,
) -> tuple[list[ReferencePeriod], list[ReferencePeriod]]:
    """Enumerate full MD/AD rows and the selected ancestry from rational degrees."""
    mansion_index, mansion_fraction = divmod(moon_degrees * 3 / 40, 1)
    first_index = int(mansion_index) % 9
    year_microseconds = YEAR_DAYS[year_basis] * DAY_MICROSECONDS
    first_start = -mansion_fraction * LORD_YEARS[first_index][1] * year_microseconds
    cycle_microseconds = 120 * year_microseconds
    cycle_index = (target_microseconds - quantize_microseconds(first_start)) // int(
        cycle_microseconds
    )
    cycle_start = first_start + cycle_index * cycle_microseconds
    major_periods = []
    sub_periods = []
    current_periods = []
    elapsed_years = 0
    for step in range(9):
        lord, years = LORD_YEARS[(first_index + step) % 9]
        period = ReferencePeriod(
            (lord,),
            cycle_start + elapsed_years * year_microseconds,
            cycle_start + (elapsed_years + years) * year_microseconds,
        )
        major_periods.append(period)
        elapsed_years += years
    candidates = major_periods
    for level in range(1, depth + 1):
        selected = next(
            period
            for period in candidates
            if quantize_microseconds(period.start_microseconds)
            <= target_microseconds
            < quantize_microseconds(period.end_microseconds)
        )
        current_periods.append(selected)
        parents = major_periods if level == 1 else [selected]
        candidates = []
        for parent in parents:
            first_child_index = next(
                index
                for index, (lord, _) in enumerate(LORD_YEARS)
                if lord == parent.lord_chain[-1]
            )
            cumulative_weight = 0
            for step in range(9):
                lord, weight = LORD_YEARS[(first_child_index + step) % 9]
                duration_microseconds = (
                    parent.end_microseconds - parent.start_microseconds
                )
                child = ReferencePeriod(
                    (*parent.lord_chain, lord),
                    parent.start_microseconds
                    + duration_microseconds * Fraction(cumulative_weight, 120),
                    parent.start_microseconds
                    + duration_microseconds * Fraction(cumulative_weight + weight, 120),
                )
                cumulative_weight += weight
                candidates.append(child)
        if level == 1:
            sub_periods = candidates
        else:
            pass
    return [*major_periods, *sub_periods], current_periods
