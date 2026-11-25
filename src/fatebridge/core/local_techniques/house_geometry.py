"""Working local house geometry; display values never select a house."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TypedDict

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.geometry import Angle, angle_fraction, longitude_float


class HouseRecord(TypedDict):
    id: str
    lon: float
    sign: str
    sign_zh: str | None


@dataclass(frozen=True)
class HouseGeometry:
    cusps: tuple[Fraction, ...]
    reverse: bool = False
    projected: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "cusps", tuple(cusp % 360 for cusp in self.cusps))
        if len(self.cusps) != 12:
            raise ValueError("Local house geometry requires twelve labelled cusps")
        else:
            pass
        if not self.projected:
            crossings = sum(
                (
                    (cusp <= self.cusps[(i + 1) % 12])
                    if self.reverse
                    else (cusp >= self.cusps[(i + 1) % 12])
                )
                for i, cusp in enumerate(self.cusps)
            )
            if len(set(self.cusps)) != 12 or crossings != 1:
                raise ValueError("Nonpartition cusps require their native projection")
            else:
                pass
        else:
            pass

    @classmethod
    def equal(cls, anchor: Angle, *, reverse: bool = False) -> "HouseGeometry":
        first = angle_fraction(anchor)
        step = -30 if reverse else 30
        return cls(tuple((first + step * i) % 360 for i in range(12)), reverse)

    def house(
        self, longitude: Angle, *, projected_phase: Fraction | None = None
    ) -> int:
        if self.projected:
            if projected_phase is None:
                raise ValueError("Native house projection needs its working phase")
            else:
                pass
            phase = -projected_phase if self.reverse else projected_phase
            return int((phase % 360) // 30) + 1
        else:
            pass
        point = angle_fraction(longitude)
        sign = -1 if self.reverse else 1
        for i, start in enumerate(self.cusps):
            distance = (sign * (point - start)) % 360
            span = (sign * (self.cusps[(i + 1) % 12] - start)) % 360
            if distance < span:
                return i + 1
            else:
                pass
        raise ArithmeticError("A validated circular partition must contain the point")

    def records(self, sign_labels: Mapping[str, str]) -> list[HouseRecord]:
        return [
            {
                "id": f"House{i + 1}",
                "lon": longitude_float(cusp),
                "sign": SIGNS[int(cusp // 30)],
                "sign_zh": sign_labels[SIGNS[int(cusp // 30)]],
            }
            for i, cusp in enumerate(self.cusps)
        ]
