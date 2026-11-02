"""Scoped raw DE441 records for unrounded, high-precision source arguments.

The source argument is exact as supplied; no physical TT/TDB conversion occurs.
The float-state reader remains separate. This context has no global file cache.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, Tuple

from fatebridge.core.astro.jpl_kinematics import RECORD_BYTES, _signature
from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.utils.errors import EphemerisSourceError


class SourceRecords:
    def __init__(self, stream: BinaryIO, path: Path, info: Dict[str, Any]) -> None:
        self.stream, self.path = stream, path
        self.signature = _signature(os.fstat(stream.fileno()))
        self.check()
        self.header = stream.read(RECORD_BYTES)
        if len(self.header) != RECORD_BYTES or self.signature[2] != info["bytes"]:
            raise EphemerisSourceError("jpl_kinematics_invalid")
        orders = [
            o
            for o in ("<", ">")
            if struct.unpack_from(o + "i", self.header, 2840)[0] == 441
        ]
        if len(orders) != 1:
            raise EphemerisSourceError("jpl_kinematics_invalid")
        self.order = orders[0]
        self.start, self.end, self.step = struct.unpack_from(
            self.order + "3d", self.header, 2652
        )
        self.au, self.emrat = struct.unpack_from(self.order + "2d", self.header, 2680)
        if (
            self.step != 32
            or self.au != 149597870.7
            or not 81 < self.emrat < 82
            or self.start != info["start_julian_day_tdb"]
            or self.end != info["end_julian_day_tdb"]
        ):
            raise EphemerisSourceError("jpl_kinematics_invalid")
        self.cache: Dict[int, Tuple[float, ...]] = {}
        self.receipts: Dict[int, Dict[str, Any]] = {}
        self.cells: set[tuple] = set()

    def check(self) -> None:
        if self.signature != _signature(
            os.fstat(self.stream.fileno())
        ) or self.signature != _signature(self.path.stat()):
            raise EphemerisSourceError("changed_during")

    def record(self, epoch: Fraction) -> Tuple[float, ...]:
        if not Fraction(self.start) <= epoch <= Fraction(self.end):
            raise EphemerisSourceError("jpl_kinematics_outside_source")
        index = min(
            int((epoch - Fraction(self.start)) // Fraction(self.step)),
            int((self.end - self.start) / self.step) - 1,
        )
        if index not in self.cache:
            self.stream.seek((index + 2) * RECORD_BYTES)
            raw = self.stream.read(RECORD_BYTES)
            self.check()
            if len(raw) != RECORD_BYTES:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            values = struct.unpack(self.order + "1018d", raw)
            if not all(math.isfinite(x) for x in values) or values[:2] != (
                self.start + index * self.step,
                self.start + (index + 1) * self.step,
            ):
                raise EphemerisSourceError("jpl_kinematics_invalid")
            self.cache[index] = values
            self.receipts[index] = {
                "index": index,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "start": values[0],
                "end": values[1],
            }
        return self.cache[index]

    def pointer(self, group: int) -> Tuple[int, int, int]:
        if not 0 <= group <= 10:
            raise EphemerisSourceError("jpl_kinematics_invalid")
        offset, count, parts = struct.unpack_from(
            self.order + "3i", self.header, 2696 + 12 * group
        )
        if not (
            3 <= offset
            and 1 <= count <= 41
            and parts in {1, 2, 4, 8, 16}
            and offset + 3 * count * parts - 1 <= 1018
        ):
            raise EphemerisSourceError("jpl_kinematics_invalid")
        return offset, count, parts

    def evidence(self) -> Dict[str, Any]:
        return {
            "filename": self.path.name,
            "header_sha256": hashlib.sha256(self.header).hexdigest(),
            "records": [self.receipts[k] for k in sorted(self.receipts)],
            "polynomial_cells": [list(cell) for cell in sorted(self.cells)],
            "source_time_scale": "TDB",
            "argument_policy": "continuous_native_numeric_argument_no_physical_TT_conversion",
            "atomic_file_read_proven": False,
            "observational_accuracy_certified": False,
        }


@contextmanager
def source_records(path: Path) -> Iterator[SourceRecords]:
    info = jpl_header(path)
    try:
        with path.open("rb") as stream:
            reader = SourceRecords(stream, path, info)
            try:
                yield reader
            finally:
                reader.check()
    except OSError as error:
        raise EphemerisSourceError("unavailable_during") from error
