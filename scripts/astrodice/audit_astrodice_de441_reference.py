"""Independently replay raw direct-access DE441 records by basis recurrence.

No collector, Clenshaw implementation, FateBridge, Swiss or third-party
ephemeris reader is imported. This verifies the declared source calculation;
the shared dynamical model and TDB-only time contract remain limitations.
"""

import argparse
import hashlib
import json
import re
import struct
from fractions import Fraction as Q
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jd(label):
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", label)
    if match is None:
        raise ValueError("Unplanned TDB calendar label")
    y, m, d, h, minute, second = map(int, match.groups())
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    months = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (
        1 <= y <= 9999
        and 1 <= m <= 12
        and 1 <= d <= months[m - 1]
        and h < 24
        and minute < 60
        and second < 60
    ):
        raise ValueError("Invalid TDB calendar fields")
    a = (14 - m) // 12
    yr, mo = y + 4800 - a, m + 12 * a - 3
    jdn = d + (153 * mo + 2) // 5 + 365 * yr + yr // 4 - yr // 100 + yr // 400 - 32045
    return Q(jdn) - Q(1, 2) + Q(h * 3600 + minute * 60 + second, 86400)


def direct_state(data, pointer, epoch):
    start, end = map(Q, struct.unpack_from("<2d", data))
    offset, n, pieces = pointer
    width = (end - start) / pieces
    block = (epoch - start) // width
    if not start <= epoch < end or not 0 <= block < pieces:
        raise ValueError("Source block does not cover the epoch")
    x = 2 * (epoch - start - block * width) / width - 1
    basis, derivative = [Q(1)], [Q(0)]
    if n > 1:
        basis.append(x)
        derivative.append(Q(1))
    for _ in range(2, n):
        derivative.append(2 * basis[-1] + 2 * x * derivative[-1] - derivative[-2])
        basis.append(2 * x * basis[-1] - basis[-2])
    positions, rates = [], []
    for axis in range(3):
        first = offset - 1 + (block * 3 + axis) * n
        c = [Q(v) for v in struct.unpack_from("<" + str(n) + "d", data, first * 8)]
        positions.append(sum((a * b for a, b in zip(c, basis)), Q(0)))
        rates.append(sum((a * b for a, b in zip(c, derivative)), Q(0)) * 2 / width)
    return positions + rates


def audit(run):
    original_header = (run / "header.bin").read_bytes()
    response = json.loads((run / "header-response.json").read_text())
    if (
        len(original_header) != 8144
        or sha(original_header) != response["sha256"]
        or response["status"] != 206
    ):
        raise ValueError("Original header identity changed")
    start, end, span = struct.unpack_from("<3d", original_header, 2652)
    if span != 32 or struct.unpack_from("<i", original_header, 2840)[0] != 441:
        raise ValueError("Unplanned original ephemeris")
    total = (int((end - start) / span) + 2) * 8144
    etag = response["headers"]["ETag"]
    if response["headers"]["Content-Range"] != f"bytes 0-8143/{total}":
        raise ValueError("Original header range changed")
    constants_raw = (run / "record-responses/constants.bin").read_bytes()
    nconst = struct.unpack_from("<i", original_header, 2676)[0]
    names = [
        original_header[252 + i * 6 : 258 + i * 6].decode().strip() for i in range(400)
    ]
    names += [
        original_header[2856 + i * 6 : 2862 + i * 6].decode().strip()
        for i in range(nconst - 400)
    ]
    constants = dict(
        zip(names, map(Q, struct.unpack_from("<" + str(nconst) + "d", constants_raw)))
    )
    au, emrat = map(Q, struct.unpack_from("<2d", original_header, 2680))
    if (
        constants["DENUM"] != 441
        or constants["LENUM"] != 441
        or constants["AU"] != au
        or constants["EMRAT"] != emrat
    ):
        raise ValueError("Original constant record and header disagree")
    pointers = [
        struct.unpack_from("<3i", original_header, 2696 + g * 12) for g in range(12)
    ]
    journal = [
        json.loads(line)
        for line in (run / "record-responses/requests.jsonl").read_text().splitlines()
    ]
    if len(journal) != 8 or [item["name"] for item in journal] != ["constants"] + [
        f"case-{i:02}" for i in range(7)
    ]:
        raise ValueError("Original planned range requests changed")
    for item in journal:
        raw = (run / "record-responses" / item["file"]).read_bytes()
        size = item["end"] - item["start"] + 1
        if (
            item["status"] != 206
            or len(raw) != size
            or sha(raw) != item["sha256"]
            or item["headers"]["ETag"] != etag
            or item["headers"]["Content-Range"]
            != f"bytes {item['start']}-{item['end']}/{total}"
        ):
            raise ValueError(
                "Raw coefficient response failed independent identity check"
            )
    reference = json.loads((run / "geometric-reference.json").read_text())
    plan = json.loads((run / "design-before-source.json").read_text())
    frozen = json.loads((run / "before-coefficient-queries.json").read_text())
    if (
        reference["design_sha256"]
        != sha((run / "design-before-source.json").read_bytes())
        or reference["design_sha256"] != frozen["design_sha256"]
        or reference["candidate_imported"]
        or reference["method_id"]
        != "independent_exact_rational_de441_geometric_clenshaw_v1"
        or reference["full_kernel_sha256_verified"]
        or len(reference["rows"]) != len(plan["conditions"])
        or len(reference["rows"]) != 7
    ):
        raise ValueError("Declared reference population/source contract changed")
    checked = 0
    for index, row in enumerate(reference["rows"]):
        if row["id"] != f"de441-geometric-{index:02}" or row["role"] != (
            "known_diagnostic_control" if index < 3 else "frozen_geometric_holdout"
        ):
            raise ValueError("Frozen condition identity or role changed")
        epoch = jd(plan["conditions"][index])
        if (
            row["date_tdb"] != plan["conditions"][index]
            or Q(row["epoch_jd_tdb_exact"]) != epoch
            or row["native_numeric_argument"] != float(epoch)
            or Q(row["argument_rounding_seconds"]) != (Q(float(epoch)) - epoch) * 86400
        ):
            raise ValueError("Original exact/binary64 epoch identity changed")
        source = (run / row["source_record_file"]).read_bytes()
        records = [source[k : k + 8144] for k in range(0, len(source), 8144)]
        record_index = (epoch - Q(start)) // 32
        if (
            len(source) != 3 * 8144
            or row["original_record_index"] != record_index
            or journal[index + 1]["start"] != (record_index + 1) * 8144
        ):
            raise ValueError("Original record selection changed")
        for k, record in enumerate(records):
            bounds = struct.unpack_from("<2d", record)
            if bounds != (
                start + (record_index - 1 + k) * 32,
                start + (record_index + k) * 32,
            ):
                raise ValueError("Original record boundaries changed")
        kernel = (run / row["kernel_path"]).read_bytes()
        if (
            len(kernel) != 5 * 8144
            or sha(kernel) != row["kernel_sha256"]
            or kernel[8144:] != constants_raw + source
        ):
            raise ValueError(
                "Diagnostic excerpt changed original constants/coefficients"
            )
        if any(
            a != b and not (i < 252 or 2652 <= i < 2668)
            for i, (a, b) in enumerate(zip(original_header, kernel[:8144]))
        ) or struct.unpack_from("<2d", kernel, 2652) != (
            start + (record_index - 1) * 32,
            start + (record_index + 2) * 32,
        ):
            raise ValueError(
                "Diagnostic excerpt header changed outside declared ranges"
            )
        for argument, field in [
            (epoch, "states_at_exact_tdb_au_and_au_per_day"),
            (Q(float(epoch)), "states_at_binary64_argument_au_and_au_per_day"),
        ]:
            g = {
                n: direct_state(records[1], pointers[n], argument)
                for n in (0, 1, 2, 9, 10)
            }
            earth = [emb - moon / (emrat + 1) for emb, moon in zip(g[2], g[9])]
            states = {
                "Mercury": g[0],
                "Venus": g[1],
                "Earth": earth,
                "Moon": [e + m for e, m in zip(earth, g[9])],
                "Sun": g[10],
            }
            if set(row[field]) != set(states):
                raise ValueError("Reference body set changed")
            for name, values in states.items():
                expected = [v / au for v in values]
                if expected != list(map(Q, row[field][name])):
                    raise ValueError(
                        "Independent coefficient evaluation differs: "
                        + row["id"]
                        + ":"
                        + name
                    )
                checked += len(values)
    return {
        "method_id": "independent_direct_basis_de441_raw_replay_v1",
        "exit_code": 0,
        "reference_rows": 7,
        "rational_components_exactly_equal": checked,
        "original_constants_independently_checked": ["DENUM", "LENUM", "AU", "EMRAT"],
        "all_original_record_bytes_and_excerpt_headers_checked": True,
        "source_full_file_sha256_verified": False,
        "tt_calendar_acceptance": False,
        "apparent_position_acceptance": False,
        "full_goal_complete": False,
        "scope": "Independent raw-format and exact arithmetic replay. Shared DE441 dynamics and nominal TDB scope; no observations, TT conversion or full apparent ephemeris certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2) + "\n")
    print(result)
