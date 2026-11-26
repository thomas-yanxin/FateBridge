"""Build the optional AA1996 Sun library from pinned native source files."""

from __future__ import annotations

import argparse
import ctypes
import json
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from importlib.resources import files
from pathlib import Path
from typing import Any

MODEL_ID = "fatebridge_moshier_aa1996_solar_v1"


def source_profile() -> dict[str, Any]:
    raw = (
        files("fatebridge").joinpath("data/astronomy/aa1996-solar-v1.json").read_bytes()
    )
    profile: dict[str, Any] = json.loads(raw)
    if profile.get("model_id") != MODEL_ID or profile.get("abi_version") != 1:
        raise ValueError("Invalid AA1996 source profile")
    return profile


def _archive(source: dict[str, str], supplied: Path | None, target: Path) -> Path:
    if supplied is not None:
        archive_bytes = supplied.read_bytes()
    else:
        with urllib.request.urlopen(source["url"], timeout=30) as response:
            archive_bytes = response.read()
    target.write_bytes(archive_bytes)
    return target


def build(
    output: Path,
    *,
    swiss_archive: Path | None = None,
    aa56_archive: Path | None = None,
    compiler: str | None = None,
) -> dict[str, int | str]:
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        raise ValueError("AA1996 source builder currently supports macOS and Linux")
    profile = source_profile()
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    archives = output / "archives"
    archives.mkdir()
    swiss = _archive(
        profile["sources"]["swiss"], swiss_archive, archives / "pyswisseph.tar.gz"
    )
    aa56 = _archive(profile["sources"]["aa56"], aa56_archive, archives / "aa56.zip")
    expected: dict[str, str] = profile["calculation_files_sha256"]
    with tarfile.open(swiss) as bundle:
        for archive_member in bundle:
            parts = Path(archive_member.name).parts
            if (
                archive_member.isfile()
                and len(parts) == 3
                and parts[1] == "libswe"
                and parts[2] in expected
            ):
                member = bundle.extractfile(archive_member)
                if member is None:
                    raise ValueError("Pinned native source member could not be read")
                with member:
                    (source / parts[2]).write_bytes(member.read())
    author = source / "author"
    author.mkdir()
    with zipfile.ZipFile(aa56) as bundle:
        for name in bundle.namelist():
            base = Path(name).name
            if "author/" + base in expected:
                (author / base).write_bytes(bundle.read(name))
    (author / "wrapper.c").write_text(profile["source_wrapper_c"])
    (author / "native_bridge.c").write_text(profile["native_bridge_c"])
    original = (source / "swemplan.c").read_text()
    needle = "int swi_moshplan2 (double J, int iplm, double *pobj)"
    if original.count(needle) != 1:
        raise ValueError("Unexpected pinned Moshier dispatch")
    patched = original.replace(needle, profile["native_declaration_c"] + "\n" + needle)
    needle = "  const struct plantbl *plan = planets[iplm];"
    if patched.count(needle) != 1:
        raise ValueError("Unexpected pinned Moshier Earth table selector")
    patched = patched.replace(
        needle,
        needle + "\n\n  if (iplm == 2) return fatebridge_aa96_native_emb(J, pobj);",
    )
    needle = "static void embofs_mosh(double tjd, double *xemb) \n{"
    if patched.count(needle) != 1:
        raise ValueError("Unexpected pinned Moshier lunar offset")
    patched = patched.replace(needle, needle + profile["lunar_replacement_c"])
    (source / "swemplan-aa1996.c").write_text(patched)
    marker = f"""#include "swephexp.h"
const char *fatebridge_aa1996_model_id(void) {{ return "{MODEL_ID}"; }}
int fatebridge_aa1996_abi_version(void) {{ return 1; }}
int fatebridge_aa1996_solar(double tt, double *out, char *error) {{
    return swe_calc(tt, SE_SUN, SEFLG_MOSEPH | SEFLG_SPEED, out, error);
}}
"""
    (source / "model_marker.c").write_text(marker)
    if compiler is None:
        apple = Path("/Library/Developer/CommandLineTools/usr/bin/clang")
        compiler = (
            str(apple) if system == "Darwin" and apple.is_file() else shutil.which("cc")
        )
    if not compiler:
        raise ValueError(
            "A C compiler is required to build the optional AA1996 library"
        )
    library = output / (
        "aa1996-solar.dylib" if system == "Darwin" else "aa1996-solar.so"
    )
    core = [
        "swedate.c",
        "swehouse.c",
        "swejpl.c",
        "swemmoon.c",
        "swemplan-aa1996.c",
        "sweph.c",
        "swephlib.c",
        "swecl.c",
        "swehel.c",
    ]
    author_sources = [
        "gplan.c",
        "ear404.c",
        "mlr404.c",
        "mlat404.c",
        "epsiln.c",
        "wrapper.c",
        "native_bridge.c",
    ]
    flags = (
        [
            "-dynamiclib",
            "-isysroot",
            "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
        ]
        if system == "Darwin"
        else ["-shared", "-fPIC", "-Wl,-Bsymbolic"]
    )
    command = [
        compiler,
        *flags,
        "-std=gnu99",
        "-fsigned-char",
        "-O2",
        "-fno-fast-math",
        "-I",
        str(source),
        *[str(source / name) for name in core],
        *[str(author / name) for name in author_sources],
        str(source / "model_marker.c"),
        "-o",
        str(library),
    ]
    if system == "Linux":
        command += ["-lm", "-ldl"]
    with (output / "build-console.txt").open("x") as log:
        result = subprocess.run(command, stdout=log, stderr=log)
    build_record = dict(
        command=command,
        returncode=result.returncode,
    )
    (output / "build.json").write_text(json.dumps(build_record, indent=2) + "\n")
    if result.returncode:
        raise RuntimeError(
            "AA1996 compilation failed; original sources and log retained"
        )
    probe = ctypes.CDLL(str(library))
    method = getattr(probe, "fatebridge_aa1996_model_id")
    method.restype = ctypes.c_char_p
    if method().decode("ascii") != MODEL_ID:
        raise ValueError("Built AA1996 model marker mismatch")
    manifest: dict[str, int | str] = dict(
        model_id=MODEL_ID,
        version=profile["version"],
        abi_version=1,
        binary=library.name,
        system=system,
        machine=platform.machine(),
        build_record="build.json",
        source_url=profile["reference"],
        source_identity_scope="Local pinned-source build receipt; not upstream signature or all-epoch accuracy certification",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New output directory; failed builds are retained",
    )
    parser.add_argument("--swiss-archive", type=Path)
    parser.add_argument("--aa56-archive", type=Path)
    parser.add_argument("--compiler")
    args = parser.parse_args()
    result = build(
        args.output,
        swiss_archive=args.swiss_archive,
        aa56_archive=args.aa56_archive,
        compiler=args.compiler,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
