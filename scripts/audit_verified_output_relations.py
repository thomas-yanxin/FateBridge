"""Check all 144 Taiyi cores and 1080 Qimen leader relations; source priority stays open."""

import argparse
import json
from pathlib import Path

from fatebridge.core.metaphysics.qimen import _qimen_zhifu_zhishi
from fatebridge.core.metaphysics.taiyi_source_alignment import count_source_assessment
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.core.qimen_evidence import _source_disagreements
from fatebridge.core.verified_outputs import (
    collect_source_conflicts,
    collect_verified_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for yin in (False, True):
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            payload = {
                "taiyi": {
                    "core_board": core,
                    "source_alignment": count_source_assessment(core),
                }
            }
            witnesses = collect_verified_outputs(payload)
            conflicts = collect_source_conflicts(payload, witnesses)
            rows.append(
                {
                    "case_id": f'{"yin" if yin else "yang"}-{ju}',
                    "payload": payload,
                    "proofs": [w.model_dump(mode="json") for w in witnesses],
                    "conflicts": conflicts,
                }
            )
    qrows = []
    for yin in (False, True):
        for ju in range(1, 10):
            for i in range(60):
                hour = (
                    "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
                )
                ju_text = f'{"阴" if yin else "阳"}遁{"一二三四五六七八九"[ju-1]}局上元'
                leader = _qimen_zhifu_zhishi(
                    hour, ju_text, dun_type="阴" if yin else "阳"
                )
                board = {
                    "ju_text": ju_text,
                    "time_ganzhi": hour,
                    "rule_trace": [
                        {
                            "rule_id": "leaders",
                            "inputs": {"time_ganzhi": hour},
                            "outputs": leader,
                        }
                    ],
                }
                # The two printed raw-door contradictions are distinct from the other
                # source conflicts requiring full plate/pattern semantics.
                if yin and (ju, hour) in {(9, "庚辰"), (4, "癸亥")}:
                    board["source_disagreements"] = _source_disagreements(board, leader)
                payload = {"qimen": board}
                witnesses = collect_verified_outputs(payload)
                qrows.append(
                    {
                        "case_id": f'{"yin" if yin else "yang"}-{ju}-{hour}',
                        "payload": payload,
                        "proofs": [w.model_dump(mode="json") for w in witnesses],
                        "conflicts": collect_source_conflicts(payload, witnesses),
                    }
                )
    result = {
        "taiyi": rows,
        "qimen": qrows,
        "summary": {
            "taiyi_cases": len(rows),
            "taiyi_verified_relations": sum(len(r["proofs"]) for r in rows),
            "taiyi_source_conflicts": sum(len(r["conflicts"]) for r in rows),
            "qimen_cases": len(qrows),
            "qimen_verified_relations": sum(len(r["proofs"]) for r in qrows),
            "qimen_raw_door_conflicts": sum(len(r["conflicts"]) for r in qrows),
        },
        "source_priority_adjudicated": False,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result["summary"]))
    return 1  # Source priority remains open; mathematical closure is a separate axis.


if __name__ == "__main__":
    raise SystemExit(main())
