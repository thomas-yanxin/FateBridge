"""Refresh the explicit research anchor catalogue from CDS SIMBAD.

Network-only acquisition; no FateBridge/Swiss imports and no production outputs
used as reference answers. Review changed astronomical records before accepting
new data. The anchor mapping is a declared research convention, not a recovered
classical star identification. Ordinary tests never call this script.
"""

import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

names = "角 亢 氐 房 心 尾 箕 斗 牛 女 虚 危 室 壁 奎 娄 胃 昴 毕 觜 参 井 鬼 柳 星 张 翼 轸".split()
ids = [
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
from urllib.parse import urlencode


def fetch(pair):
    name, ident = pair
    url = "https://simbad.cds.unistra.fr/simbad/sim-id?" + urlencode(
        {"Ident": ident, "output.format": "ASCII"}
    )
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "30", url]
    ).decode()
    pos = re.search(
        r"Coordinates\(ICRS,ep=J2000,eq=2000\):\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([+-]\d+)\s+(\d+)\s+([\d.]+)",
        raw,
    )
    pm = re.search(r"Proper motions:\s+([\d.+-]+)\s+([\d.+-]+)", raw)
    px = re.search(r"Parallax:\s+([\d.+-]+)", raw)
    rv = re.search(r"Radial Velocity:\s+([\d.+-]+)", raw)
    if not all([pos, pm, px, rv]):
        raise RuntimeError(f"incomplete {ident}")
    brief = "\n".join(raw.splitlines()[:17]) + "\n"
    return {
        "mansion": name + "宿",
        "star": ident,
        "source_url": url,
        "source_excerpt": brief,
        "excerpt_sha256": hashlib.sha256(brief.encode()).hexdigest(),
        "record": [float(v) for v in pos.groups()]
        + [float(v) for v in pm.groups()]
        + [float(rv[1]), float(px[1])],
    }


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(fetch, zip(names, ids)))
path = Path(__file__).resolve().parents[1] / "src/fatebridge/data/guolao/sources.json"
path.write_text(
    json.dumps(
        {
            "source": "CDS SIMBAD, ICRS positions at J2000, proper motions in mas/yr (RA*cos(dec)); parallax mas, radial velocity km/s",
            "mapping_scope": "Explicit research anchor set; not a reconstruction of the Tohoku classical edition. Epoch crossings are sorted by actual right ascension.",
            "stars": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
catalogue = path.parent / "sefstars.txt"
lines = [
    "# FateBridge research anchor catalogue. Numerical astronomical facts from CDS SIMBAD.",
    "# ICRS epoch J2000; pmRA*cos(dec), pmDec and parallax in mas; RV in km/s.",
    "# Source URLs, transcribed records and receipt hashes: sources.json. Not a classical-era star table.",
]
for index, star in enumerate(rows):
    lines.append(
        f"FBJ{index:02},FBJ{index:02},ICRS,"
        + ",".join(str(v) for v in star["record"])
        + ",0"
    )
catalogue.write_text("\n".join(lines) + "\n", encoding="utf-8")
data = json.loads(path.read_text())
data["catalogue_sha256"] = hashlib.sha256(catalogue.read_bytes()).hexdigest()
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Saved", len(rows), path)
