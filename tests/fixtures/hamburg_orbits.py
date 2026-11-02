"""Controlled input orbits, adapted from Swiss's published seorbel example.

These are test inputs, not new observational or prediction reference values.
Source: https://github.com/aloistr/swisseph/blob/master/ephe/seorbel.txt
"""

from pathlib import Path

ROWS = (
    "J1900,J1900,163.7409,40.99837,0.00460,171.4333,129.8325,1.0833,Cupido",
    "J1900,J1900,27.6496,50.66744,0.00245,148.1796,161.3339,1.0500,Hades",
    "J1900,J1900,165.1232,59.21436,0.00120,299.0440,0,0,Zeus",
    "J1900,J1900,169.0193,64.81690,0.00305,208.8801,0,0,Kronos",
    "J1900,J1900,138.0533,70.29949,0,0,0,0,Apollon",
    "J1900,J1900,351.3350,73.62765,0,0,0,0,Admetos",
    "J1900,J1900,55.8983,77.25568,0,0,0,0,Vulcanus",
    "J1900,J1900,165.5163,83.66907,0,0,0,0,Poseidon",
)


def write_orbits(directory: Path, *, cupido_anomaly: str = "163.7409") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "seorbel.txt"
    rows = list(ROWS)
    rows[0] = rows[0].replace("163.7409", cupido_anomaly)
    path.write_text("\n".join(rows) + "\n", encoding="ascii")
    return path
