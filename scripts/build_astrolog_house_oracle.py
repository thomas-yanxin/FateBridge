"""Build the pinned Astrolog house algorithms with both ephemerides disabled.

Run this in a dedicated checkout of v8.00, commit 5bf172ea231c4b6ea3d7e09ca307571354a41e8a.
Only configuration defines are changed; the mathematical source is checked
against the pinned Git objects. Upstream copyright notices remain intact.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

COMMIT = "5bf172ea231c4b6ea3d7e09ca307571354a41e8a"
SOURCES = "astrolog atlas calc charts0 charts1 charts2 charts3 data express general intrpret io matrix".split()
HARNESS = r"""#include "astrolog.h"
int main(int argc, char **argv) {
 if (argc != 5) return 2;
 is.RA=atof(argv[1]); AA=atof(argv[2]); is.OB=atof(argv[3]);
 is.rSid=0.0; us.fPolarAsc=fFalse;
 is.Asc=CuspAscendant(); is.MC=CuspMidheaven(); is.EP=CuspEastPoint();
 real asc=is.Asc, mc=is.MC;
 ComputeHouses(atoi(argv[4]));
 printf("{\"ascendant\":%.17g,\"midheaven\":%.17g,\"effective_system\":%d,\"cusps\":[",asc,mc,is.nHouseSystem);
 for(int i=1;i<=12;i++) printf(i==12?"%.17g]}\n":"%.17g,",chouse[i]);
 return 0;
}
"""


def build(source: Path, compiler: str):
    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "safe.directory=" + str(source), "-C", str(source), *args]
        )

    if git("rev-parse", "HEAD").decode().strip() != COMMIT:
        raise RuntimeError("Expected the exact pinned Astrolog commit")
    hashes = {}
    for name in SOURCES + ["astrolog", "extern"]:
        suffix = ".h" if name == "extern" else ".cpp"
        filename = name + suffix
        raw = (source / filename).read_bytes()
        if raw != git("show", "HEAD:" + filename):
            raise RuntimeError("Modified mathematical source: " + filename)
        hashes[filename] = hashlib.sha256(raw).hexdigest()
    header = git("show", "HEAD:astrolog.h")
    for flag in ("SWISS", "PLACALC", "GRAPH", "X11", "PS", "META", "SVG", "WIRE"):
        pattern = rb"(?m)^#define " + flag.encode() + rb" "
        header, count = re.subn(
            pattern,
            b"// House oracle disables: #define " + flag.encode() + b" ",
            header,
        )
        if count != 1:
            raise RuntimeError("Unexpected upstream configuration: " + flag)
    (source / "astrolog.h").write_bytes(header)
    (source / "house_oracle.cpp").write_text(HARNESS)
    builddir = source / ".house-oracle-build"
    builddir.mkdir(exist_ok=True)
    commands = []
    objects = []
    for name in SOURCES + ["house_oracle"]:
        obj = builddir / (name + ".o")
        cmd = [compiler, "-O2", "-Wno-write-strings", "-Wno-narrowing", "-Wno-comment"]
        if name == "astrolog":
            cmd.append("-Dmain=astrolog_cli_main")
        cmd += ["-c", str(source / (name + ".cpp")), "-o", str(obj)]
        commands.append(cmd)
        objects.append(str(obj))
    executable = source / "house_oracle"
    commands.append([compiler, "-o", str(executable), *objects, "-lm"])
    logs = []
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        logs.append(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr)
    (builddir / "build.log").write_text("\n".join(logs))
    symbols = subprocess.check_output(["nm", "-g", str(executable)], text=True)
    if re.search(r"\bswe_\w+", symbols):
        raise RuntimeError("Swiss symbols found in independent executable")
    metadata = {
        "upstream": "https://github.com/CruiserOne/Astrolog",
        "version": "8.00",
        "commit": COMMIT,
        "original_source_sha256": hashes,
        "configured_header_sha256": hashlib.sha256(header).hexdigest(),
        "harness_sha256": hashlib.sha256(HARNESS.encode()).hexdigest(),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "swiss_compiled": False,
        "placalc_compiled": False,
        "house_algorithm_source": "calc.cpp and matrix.cpp, unmodified",
        "compiler": subprocess.check_output(
            [compiler, "--version"], text=True
        ).splitlines()[0],
        "commands": commands,
        "scope": "Fixed ARMC/latitude/obliquity house geometry; no Matrix planetary positions or time conversion",
    }
    (source / "house_oracle-build.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    args = parser.parse_args()
    result = build(args.source_dir.resolve(), args.compiler)
    print("Built pinned independent house oracle", result["executable_sha256"])
