"""Check all selected image identities and every retained source tile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/fatebridge/data/sukuyo_printed_pages.json"
FIXTURE = ROOT / "tests/data/sukuyo-printed-before-production-v71.json"


def verify_primary(captures: Path | None = None) -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    before = json.loads(FIXTURE.read_bytes())
    sha = lambda value: hashlib.sha256(value).hexdigest()
    if sha(raw) != before["source_bundle_sha256"] or data != before["expected_data"]:
        raise ValueError("所选印页记录与修改前参考不一致")
    checked = 0
    if captures is not None:
        for name, digest in before["raw_tile_files_sha256"].items():
            if sha((captures / name).read_bytes()) != digest:
                raise ValueError("实际图砖字节指纹不一致")
            checked += 1
        for frame in data["printed_frames"]:
            image = captures / (frame["id"] + "-level12.png")
            if sha(image.read_bytes()) != frame["assembled_png_sha256"]:
                raise ValueError("所选层整页图像指纹不一致")
        roi = captures / "T1644-0196-a12-native-roi.png"
        if sha(roi.read_bytes()) != data["native_a12_ROI"]["png_sha256"]:
            raise ValueError("所选原分辨率局部指纹不一致")
        for item in data["followup_native_reference"]["additional_native_ROIs"]:
            if sha((captures / item["png_file"]).read_bytes()) != item["png_sha256"]:
                raise ValueError("补充原分辨率局部指纹不一致")
    return {
        "source_bundle_sha256": sha(raw),
        "selected_print_pages": len(data["printed_frames"]),
        "selected_observations": len(data["root_selected_observations"]),
        "raw_tile_files_actually_read": checked,
        "independent_human_or_complete_critical_edition_accepted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_primary(args.captures), ensure_ascii=False, indent=2))
