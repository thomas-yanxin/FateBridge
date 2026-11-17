"""Scalar APIs used by FateBridge; upstream pyerfa has no PEP 561 marker."""

from collections.abc import Sequence
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

class _Version(Protocol):
    erfa_version: str
    sofa_version: str

version: _Version
__version__: str

_VectorLike = Sequence[float] | NDArray[np.float64]

class _PositionVelocity(Protocol):
    def __getitem__(self, key: Literal["p", "v"]) -> NDArray[np.float64]: ...

def pvtob(
    elong: float, phi: float, hm: float, xp: float, yp: float, sp: float, theta: float
) -> _PositionVelocity: ...
def gc2gde(
    a: float, f: float, xyz: _VectorLike
) -> tuple[np.float64, np.float64, np.float64]: ...
def numat(epsa: float, dpsi: float, deps: float) -> NDArray[np.float64]: ...
def s06(date1: float, date2: float, x: float, y: float) -> np.float64: ...
def eors(
    rnpb: Sequence[Sequence[float]] | NDArray[np.float64], s: float
) -> np.float64: ...
def pnm06a(date1: float, date2: float) -> NDArray[np.float64]: ...
def obl06(date1: float, date2: float) -> np.float64: ...
def nut06a(date1: float, date2: float) -> tuple[np.float64, np.float64]: ...
def ld(
    bm: float, p: _VectorLike, q: _VectorLike, e: _VectorLike, em: float, dlim: float
) -> NDArray[np.float64]: ...
def ab(
    pnat: _VectorLike, v: _VectorLike, s: float, bm1: float
) -> NDArray[np.float64]: ...
