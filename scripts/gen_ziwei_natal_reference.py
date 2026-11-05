"""Freeze whole natal charts from an independently installed iztro 2.5.8.

No FateBridge imports or expected-value rewriting. Cases are chosen before
comparison, including all sexagenary years, month/hour pairs and leap halves.
Install with npm --ignore-scripts in a temporary directory, then pass --iztro.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

CONFIG = dict(
    yearDivide="normal",
    horoscopeDivide="normal",
    ageDivide="normal",
    dayDivide="current",
    algorithm="default",
)
TARGET = Path(__file__).resolve().parents[1] / "tests/data/ziwei_independent"


def cases() -> list[dict]:
    out = []
    for year in range(1984, 2044):
        for hour in range(12):
            out.append(
                dict(
                    id=f"cycle/{year}/{hour}",
                    lunar=f"{year}-{hour + 1}-{(1, 2, 15, 16, 29)[(year + hour) % 5]}",
                    hour=hour,
                    gender="男" if (year + hour) % 2 else "女",
                    leap=False,
                )
            )
    for month in range(1, 13):
        for hour in range(12):
            out.append(
                dict(
                    id=f"month_hour/{month}/{hour}",
                    lunar=f"1992-{month}-13",
                    hour=hour,
                    gender="男" if hour % 2 else "女",
                    leap=False,
                )
            )
    for year, month in ((1984, 10), (2023, 2), (2025, 6), (2033, 11)):
        for day in (1, 15, 16, 29):
            for hour in range(12):
                out.append(
                    dict(
                        id=f"leap/{year}/{day}/{hour}",
                        lunar=f"{year}-{month}-{day}",
                        hour=hour,
                        gender="男" if hour % 2 else "女",
                        leap=True,
                    )
                )
    for solar in (
        "1933-7-22",
        "1954-12-1",
        "1978-9-2",
        "2002-2-8",
        "1995-2-3",
        "1986-1-30",
    ):
        for hour in (0, 5, 11, 12):
            out.append(
                dict(
                    id=f"solar/{solar}/{hour}",
                    solar=solar,
                    hour=hour,
                    gender="男" if hour % 2 else "女",
                )
            )
    return out


SCRIPT = r"""
const fs = require('fs'), path = require('path');
const root = process.argv[1];
if (JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).version !== '2.5.8')
  throw Error('Reference version must be 2.5.8');
const {astro} = require(root);
astro.config(JSON.parse(process.argv[2]));
const inputs = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = inputs.map(input => {
  const c = input.lunar
    ? astro.byLunar(input.lunar, input.hour, input.gender, input.leap, true, 'zh-CN')
    : astro.bySolar(input.solar, input.hour, input.gender, true, 'zh-CN');
  if (input.lunar) {
    const r=c.rawDates.lunarDate;
    if (`${r.lunarYear}-${r.lunarMonth}-${r.lunarDay}` !== input.lunar || r.isLeap !== input.leap)
      throw Error('Reference normalized an invalid input: '+input.id);
  }
  const stars = {};
  for (const p of c.palaces)
    for (const s of [...p.majorStars, ...p.minorStars, ...p.adjectiveStars]) {
      if (stars[s.name]) throw Error('Duplicate reference star '+s.name);
      stars[s.name] = [p.earthlyBranch, s.brightness || null, s.mutagen ? '化'+s.mutagen : null];
    }
  return {input, solar: c.solarDate, lunar: c.rawDates.lunarDate,
    ming:c.earthlyBranchOfSoulPalace, shen:c.earthlyBranchOfBodyPalace,
    ju:c.fiveElementsClass, soul:c.soul, body:c.body, stars,
    palaces:c.palaces.map(p=>({name:p.name, ganzhi:p.heavenlyStem+p.earthlyBranch,
      daxian:p.decadal.range, changsheng:p.changsheng12, boshi:p.boshi12,
      jiangqian:p.jiangqian12, suiqian:p.suiqian12}))};
});
process.stdout.write(JSON.stringify(output));
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iztro", required=True, type=Path)
    args = parser.parse_args()
    with urlopen("https://registry.npmjs.org/iztro/2.5.8", timeout=30) as response:
        registry = json.load(response)
    records = json.loads(
        subprocess.check_output(
            ["node", "-e", SCRIPT, str(args.iztro.resolve()), json.dumps(CONFIG)],
            input=json.dumps(cases()).encode(),
        )
    )
    target = TARGET / "natal_iztro_2_5_8.json"
    # One case per line keeps the whole-chart corpus compact and auditable.
    target.write_text(
        "[\n"
        + ",\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records)
        + "\n]\n",
        encoding="utf-8",
    )
    manifest = {
        "version": "ziwei_natal_reference_v1",
        "oracle": "iztro",
        "oracle_version": "2.5.8",
        "source": "https://github.com/SylarLong/iztro/tree/2.5.8",
        "npm_integrity": registry["dist"]["integrity"],
        "npm_git_head": registry.get("gitHead"),
        "config": CONFIG,
        "case_count": len(records),
        "selection": "Predeclared 60-year/hour, month/hour and leap-half grids; all cases retained",
        "limits": "Software implementation comparison, not independent classical adjudication or real-world validation",
        "files": [
            {
                "path": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        ],
    }
    (TARGET / "natal_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Frozen {len(records)} whole natal charts from iztro 2.5.8")


if __name__ == "__main__":
    main()
