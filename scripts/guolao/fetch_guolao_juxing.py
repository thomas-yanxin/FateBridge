"""Refresh the research anchor catalogue from CDS SIMBAD."""

import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlencode

MANSION_NAMES = "角 亢 氐 房 心 尾 箕 斗 牛 女 虚 危 室 壁 奎 娄 胃 昴 毕 觜 参 井 鬼 柳 星 张 翼 轸".split()
SIMBAD_STAR_IDS = [
    "alpha Vir",
    "kappa Vir",
    "alpha2 Lib",
    "pi Sco",
    "sigma Sco",
    "mu1 Sco",
    "gamma Sgr",
    "phi Sgr",
    "beta Cap",
    "epsilon Aqr",
    "beta Aqr",
    "alpha Aqr",
    "alpha Peg",
    "gamma Peg",
    "zeta And",
    "beta Ari",
    "35 Ari",
    "17 Tau",
    "epsilon Tau",
    "lambda Ori",
    "delta Ori",
    "mu Gem",
    "theta Cnc",
    "delta Hya",
    "alpha Hya",
    "upsilon1 Hya",
    "alpha Crt",
    "gamma Crv",
]


class SimbadAnchor(TypedDict):
    mansion: str
    star: str
    source_url: str
    source_excerpt: str
    excerpt_sha256: str
    record: list[float]


def fetch_anchor(mansion_and_star: tuple[str, str]) -> SimbadAnchor:
    mansion_name, star_id = mansion_and_star
    url = "https://simbad.cds.unistra.fr/simbad/sim-id?" + urlencode(
        {"Ident": star_id, "output.format": "ASCII"}
    )
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "30", url]
    ).decode()
    coordinates = re.search(
        r"Coordinates\(ICRS,ep=J2000,eq=2000\):\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([+-]\d+)\s+(\d+)\s+([\d.]+)",
        raw,
    )
    proper_motion = re.search(r"Proper motions:\s+([\d.+-]+)\s+([\d.+-]+)", raw)
    parallax = re.search(r"Parallax:\s+([\d.+-]+)", raw)
    radial_velocity = re.search(r"Radial Velocity:\s+([\d.+-]+)", raw)
    if (
        coordinates is None
        or proper_motion is None
        or parallax is None
        or radial_velocity is None
    ):
        raise ValueError(f"Incomplete SIMBAD anchor record for {star_id}")
    else:
        pass
    brief = "\n".join(raw.splitlines()[:17]) + "\n"
    return {
        "mansion": mansion_name + "宿",
        "star": star_id,
        "source_url": url,
        "source_excerpt": brief,
        "excerpt_sha256": hashlib.sha256(brief.encode()).hexdigest(),
        "record": [float(v) for v in coordinates.groups()]
        + [float(v) for v in proper_motion.groups()]
        + [float(radial_velocity[1]), float(parallax[1])],
    }


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        anchors = list(
            pool.map(fetch_anchor, zip(MANSION_NAMES, SIMBAD_STAR_IDS, strict=True))
        )
    source_path = (
        Path(__file__).resolve().parents[2] / "src/fatebridge/data/guolao/sources.json"
    )
    catalogue_path = source_path.with_name("sefstars.txt")
    catalogue_lines = [
        "# FateBridge research anchor catalogue. Numerical astronomical facts from CDS SIMBAD.",
        "# ICRS epoch J2000; pmRA*cos(dec), pmDec and parallax in mas; RV in km/s.",
        "# Source URLs, transcribed records and receipt hashes: sources.json. Not a classical-era star table.",
    ]
    for anchor_index, anchor in enumerate(anchors):
        catalogue_lines.append(
            f"FBJ{anchor_index:02},FBJ{anchor_index:02},ICRS,"
            + ",".join(str(coordinate) for coordinate in anchor["record"])
            + ",0"
        )
    catalogue_bytes = ("\n".join(catalogue_lines) + "\n").encode("utf-8")
    catalogue_path.write_bytes(catalogue_bytes)
    source_path.write_text(
        json.dumps(
            {
                "source": "CDS SIMBAD, ICRS positions at J2000, proper motions in mas/yr (RA*cos(dec)); parallax mas, radial velocity km/s",
                "mapping_scope": "Explicit research anchor set; not a reconstruction of the Tohoku classical edition. Epoch crossings are sorted by actual right ascension.",
                "stars": anchors,
                "catalogue_sha256": hashlib.sha256(catalogue_bytes).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Saved", len(anchors), source_path)


if __name__ == "__main__":
    main()
else:
    pass
