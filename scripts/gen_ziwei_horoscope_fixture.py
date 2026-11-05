#!/usr/bin/env python3
"""Generate a pinned iztro 2.5.8 oracle, including actual active palaces.

npm install --prefix /tmp/iztro-oracle iztro@2.5.8
python scripts/gen_ziwei_horoscope_fixture.py \
  --iztro /tmp/iztro-oracle/node_modules/iztro

The old py-iztro fixture recorded monthly/daily/hourly calendar branches,
which are not active palace branches. Always resolve a scope's .index into
chart.palaces. Preserve FateBridge's late-zi=current convention and normal
lunar year/month/age boundaries. No production code is imported here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CASES = [
    ("m_1994", "1994-8-23", 7, "男", "2026-6-19", 7),
    ("f_1988", "1988-2-29", 3, "女", "2025-10-1", 3),
    ("m_2001", "2001-11-5", 11, "男", "2030-1-15", 11),
    ("reported_flow", "1990-5-15", 5, "男", "2026-10-9", 5),
    ("before_lunar_new_year", "1990-5-15", 5, "女", "2026-2-5", 5),
    ("after_lunar_new_year", "1990-5-15", 5, "女", "2026-2-18", 5),
    ("birth_before_lunar_new_year", "1990-1-1", 5, "男", "2026-1-15", 5),
    ("late_zi", "2000-12-10", 12, "男", "2026-10-9", 12),
    ("childhood_one", "2024-2-10", 0, "男", "2024-2-10", 0),
    ("childhood_two", "2024-2-10", 0, "女", "2025-2-1", 0),
    ("childhood_three", "2024-2-10", 0, "男", "2026-2-18", 0),
    ("birth_leap_first_half", "2023-3-23", 5, "男", "2026-10-9", 5),
    ("birth_leap_second_half", "2023-4-10", 5, "女", "2026-10-9", 5),
    ("target_leap_first_half", "1990-5-15", 5, "男", "2023-3-23", 5),
    ("target_leap_second_half", "1990-5-15", 5, "女", "2023-4-10", 5),
    ("historical_lunar_1933", "1933-7-22", 5, "男", "2026-10-9", 5),
    ("historical_lunar_1954", "1954-12-1", 5, "女", "2026-10-9", 5),
    ("historical_lunar_1978", "1978-9-2", 5, "男", "2026-10-9", 5),
]
CONFIG = dict(
    yearDivide="normal",
    horoscopeDivide="normal",
    ageDivide="normal",
    dayDivide="current",
    algorithm="default",
)
SCRIPT = r"""
const fs=require('fs');
const path=require('path');
const mod=process.argv[1];
if(JSON.parse(fs.readFileSync(path.join(mod,'package.json'),'utf8')).version!=='2.5.8')
  throw new Error('Oracle version must be iztro 2.5.8');
const {astro}=require(mod);astro.config(JSON.parse(process.argv[2]));
const cases=JSON.parse(fs.readFileSync(0,'utf8'));const out={};
for(const [label,bdate,bidx,gender,tdate,tidx] of cases){
  const chart=astro.bySolar(bdate,bidx,gender,true,'zh-CN');
  const h=chart.horoscope(tdate,tidx);const scopes={};
  for(const [name,attr] of [['大限','decadal'],['小限','age'],['流年','yearly'],['流月','monthly'],['流日','daily'],['流时','hourly']]){
    const scope=h[attr];
    if(!chart.palaces[scope.index]) throw new Error(label+'/'+name+' unsupported index');
    scopes[name]={branch:chart.palaces[scope.index].earthlyBranch,mutagen:scope.mutagen};
  }
  out[label]={birth:{date:bdate,time_index:bidx,gender},target:{date:tdate,time_index:tidx},nominal_age:h.age.nominalAge,scopes,oracle:{name:'iztro',version:'2.5.8',config:JSON.parse(process.argv[2])}};
}
process.stdout.write(JSON.stringify(out));
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iztro", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(
        subprocess.check_output(
            ["node", "-e", SCRIPT, str(args.iztro.resolve()), json.dumps(CONFIG)],
            input=json.dumps(CASES).encode(),
        )
    )
    out = (
        Path(__file__).resolve().parents[1]
        / "tests/data/ziwei_horoscope_reference.json"
    )
    out.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(fixture)} independent cases to {out}")


if __name__ == "__main__":
    main()
