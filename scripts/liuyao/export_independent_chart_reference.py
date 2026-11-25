"""Run the unmodified, pinned third-party implementation without FateBridge."""

import argparse
import gzip
import hashlib
import importlib.metadata
import itertools
import json
import pathlib
import subprocess
import sys

import ichingpy as icp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--git", default="git")
    args = parser.parse_args()
    repository = args.reference_repo.resolve()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        [args.git, "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    assert commit == "4eb8c0f7ba49fcd14d062be04a1bec8ba7554139"
    subprocess.run(
        [args.git, "diff", "--exit-code", "HEAD", "--", "src"],
        cwd=repository,
        check=True,
    )
    installed = pathlib.Path(icp.__file__).parent
    for source_path in (repository / "src/ichingpy").rglob("*"):
        if source_path.is_file() and "__pycache__" not in source_path.parts:
            assert (
                source_path.read_bytes()
                == (
                    installed / source_path.relative_to(repository / "src/ichingpy")
                ).read_bytes()
            )
        else:
            pass
    engine = icp.SixLinesDivinationEngine()
    rows = []
    spirit_rows = []
    for tosses in itertools.product((6, 7, 8, 9), repeat=6):
        hexagram = icp.Hexagram.from_binary([n - 6 for n in tosses])
        engine.execute(hexagram)
        original = hexagram.interpretation
        changed = original.transformed
        row = {
            "coins": list(tosses),
            "current_code": "".join(str(n % 2) for n in hexagram.values),
            "changed_code": "".join(str(n % 2) for n in hexagram.transformed.values),
            "moving_lines": [
                i + 1 for i, line in enumerate(hexagram.lines) if line.is_transform
            ],
            "palace": original.palace.label,
            "palace_element": original.palace.phase.label,
            "changed_palace": changed.palace.label,
            "changed_palace_element": changed.palace.phase.label,
            "lines": [
                {
                    "branch": line.branch.label,
                    "element": line.branch.phase.label,
                    "stem": line.stem.label,
                    "liuqin": line.relative.label,
                    "shi_ying": line.role.label if line.role is not None else "",
                    "changed_branch": transformed.branch.label,
                    "changed_stem": transformed.stem.label,
                    "changed_liuqin": transformed.relative.label,
                }
                for line, transformed in zip(original.lines, changed.lines, strict=True)
            ],
        }
        rows.append(row)
        if not row["moving_lines"]:
            for stem in icp.HeavenlyStem:
                engine.assign_spirits(original, stem)
                spirit_rows.append(
                    {
                        "code": row["current_code"],
                        "day_stem": stem.label,
                        "spirits": [line.spirit.label for line in original.lines],
                    }
                )
        else:
            pass
    assert len(rows) == 4096 and len(spirit_rows) == 640
    reference = {
        "schema": "liuyao-independent-reference.v1",
        "source": {
            "repository": "https://github.com/JinyangWang27/ichingpy",
            "commit": commit,
            "version": importlib.metadata.version("ichingpy"),
            "code_convention": "bottom-to-top; status = coin sum - 6",
            "scope": "Finite common chart substrate only; no calendar, judgment or predictive validation.",
        },
        "rows": rows,
        "spirit_rows": spirit_rows,
    }
    raw = (
        json.dumps(reference, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    (work / "reference.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    receipt = {
        "python": sys.version,
        "executable": sys.executable,
        "packages": {
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
        "commit": commit,
        "reference_sha256": hashlib.sha256(raw).hexdigest(),
        "compressed_sha256": hashlib.sha256(
            (work / "reference.json.gz").read_bytes()
        ).hexdigest(),
        "source_files": {
            str(p.relative_to(repository)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((repository / "src").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        },
        "cases": len(rows),
        "spirit_cases": len(spirit_rows),
    }
    (work / "source.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "cases": len(rows),
                "spirit_cases": len(spirit_rows),
                "reference_sha256": receipt["reference_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
else:
    pass
