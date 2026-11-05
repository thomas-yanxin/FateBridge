"""Publish frozen Liu Yao profiles after source and erratum verification.

Each profile keeps its original fixture, output name, hash manifest and erratum
policy. Scan, month-break, penalty and moving-Si adjudication have specialized
builders and are intentionally not generalized here.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.liuyao.liuyao_quote_collation import apply_quote_errata

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    "cessation": ("liuyao_cessation_v17", "liuyao-cessation-v17.json", "sha256", True),
    "clash": ("liuyao_clash_v10", "liuyao-clash-v10.json", "sha256", False),
    "control": ("liuyao_control_v9", "liuyao-control-v9.json", "sha256", False),
    "fanfu": ("liuyao_fanfu_v6", "liuyao-fanfu-v6.json", "sha256", False),
    "generation": (
        "liuyao_generation_v11",
        "liuyao-generation-v11.json",
        "sha256",
        False,
    ),
    "growth": ("liuyao_growth_v18", "liuyao-growth-v18.json", "sha256", False),
    "hidden": ("liuyao_hidden_v14", "liuyao-hidden-v14.json", "sha256", False),
    "metal_moving": (
        "liuyao_metal_moving_v34",
        "liuyao-metal-moving-v34.json",
        "files_sha256",
        False,
    ),
    "metal_own_si": (
        "liuyao_metal_own_si_v35",
        "liuyao-metal-own-si-v35.json",
        "files_sha256",
        False,
    ),
    "progression": (
        "liuyao_progression_v8",
        "liuyao-progression-v8.json",
        "sha256",
        False,
    ),
    "rescue": ("liuyao_rescue_v12", "liuyao-rescue-v12.json", "sha256", False),
    "role": ("liuyao_effects_v4", "liuyao-effects-v4.json", "sha256", False),
    "routing": ("liuyao_routing_v13", "liuyao-routing-v13.json", "sha256", False),
    "stage": ("liuyao_stages_v15", "liuyao-stages-v15.json", "sha256", True),
    "strength": ("liuyao_strength_v5", "liuyao-strength-v5.json", "sha256", True),
    "void_control": (
        "liuyao_void_control_v31",
        "liuyao-void-control-v31.json",
        "sha256",
        False,
    ),
    "void": ("liuyao_void_v7", "liuyao-void-v7.json", "sha256", False),
}


def build_profile(name: str):
    reference_name, output_name, hash_key, has_errata = PROFILES[name]
    reference = ROOT / "tests/fixtures" / reference_name
    frozen = json.loads((reference / "freeze.json").read_text(encoding="utf-8"))
    for file, digest in frozen[hash_key].items():
        if hashlib.sha256((reference / file).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen {name} reference changed: {file}")
    original = reference / "profile.json"
    profile = json.loads(original.read_text(encoding="utf-8"))
    source = (reference / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError(f"{name} source escaped fixtures")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError(f"Original {name} scan changed")
    return (
        apply_quote_errata(profile, root=ROOT, original=original, artifact=output_name)
        if has_errata
        else profile
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="*", choices=PROFILES)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name in args.profiles or PROFILES:
        text = json.dumps(build_profile(name), ensure_ascii=False, indent=2) + "\n"
        output = ROOT / "src/fatebridge/data/classical" / PROFILES[name][1]
        if args.check:
            if output.read_text(encoding="utf-8") != text:
                raise SystemExit(f"{name} profile is stale")
        else:
            output.write_text(text, encoding="utf-8")
        print(f"{name}: frozen profile, original scan and applicable errata verified")


if __name__ == "__main__":
    main()
