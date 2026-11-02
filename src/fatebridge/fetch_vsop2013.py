"""Build the optional named VSOP2013 Sun library from pinned source bytes.

The coefficients and full ERFA time conversion are embedded in the library.
Only its checked Sun ABI is public. Failed builds and original sources remain
in the explicitly requested new output directory.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
from importlib.resources import files
from pathlib import Path
from typing import Any

MODEL_ID = "fatebridge_vsop2013_solar_v1"
# Reviewed full profile, including the declared range and qualified source graph.
PROFILE_CONTENT_SHA256 = (
    "ed5c1a4c97586fa37df934b387f51a81ba73260a337fe6bebbd5e14b783f8018"
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate VSOP2013 source profile key")
        result[key] = value
    return result


CORE = (
    "swedate.c",
    "swehouse.c",
    "swejpl.c",
    "swemmoon.c",
    "swemplan-vsop2013.c",
    "sweph.c",
    "swephlib.c",
    "swecl.c",
    "swehel.c",
)
CI0 = (
    4.402608631669,
    3.176134461576,
    1.753470369433,
    6.203500014141,
    4.091360003050,
    1.713740719173,
    5.598641292287,
    2.805136360408,
    2.326989734620,
    0.599546107035,
    0.874018510107,
    5.481225395663,
    5.311897933164,
    0.0,
    5.19846640063,
    1.62790513602,
    2.35555563875,
)
CI1 = (
    26087.90314068555,
    10213.28554743445,
    6283.075850353215,
    3340.612434145457,
    1731.170452721855,
    1704.450855027201,
    1428.948917844273,
    1364.756513629990,
    1361.923207632842,
    529.6909615623250,
    213.2990861084880,
    74.78165903077800,
    38.13297222612500,
    0.3595362285049309,
    77713.7714481804,
    84334.6615717837,
    83286.9142477147,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_profile() -> tuple[dict[str, Any], str]:
    raw = (
        files("fatebridge")
        .joinpath("data/astronomy/vsop2013-solar-v1.json")
        .read_bytes()
    )
    profile: dict[str, Any] = json.loads(raw, object_pairs_hook=_unique_object)
    content = json.dumps(
        profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if hashlib.sha256(content).hexdigest() != PROFILE_CONTENT_SHA256:
        raise ValueError("Unreviewed VSOP2013 source profile content")
    return profile, hashlib.sha256(raw).hexdigest()


def _acquire(sources: dict[str, Any], folder: Path, supplied: Path | None) -> None:
    folder.mkdir()
    for name, identity in sources.items():
        if supplied is None:
            with urllib.request.urlopen(identity["url"], timeout=60) as response:
                data = response.read()
        else:
            data = (supplied / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != identity["sha256"]:
            raise ValueError(f"VSOP2013 upstream source bytes differ: {name}")
        with (folder / name).open("xb") as stream:
            stream.write(data)


def _pack_series(original: Path, output: Path) -> dict[str, Any]:
    terms = []
    series = []
    removed = []
    with original.open(encoding="ascii") as stream:
        while line := stream.readline():
            ip, iv, power, count = [
                int(line[a:b]) for a, b in ((9, 12), (12, 15), (15, 18), (18, 25))
            ]
            if ip != 3 or not 1 <= iv <= 6 or not 0 <= power <= 20:
                raise ValueError("Invalid original VSOP2013 EMB series header")
            series.append((iv, power, count))
            for rank in range(1, count + 1):
                text = stream.readline().rstrip("\n")
                if len(text) != 116 or int(text[:5]) != rank:
                    raise ValueError("Invalid original VSOP2013 term record")
                args: list[int] = []
                pos = 6
                for n, width in ((4, 3), (5, 3), (4, 4), (1, 6), (3, 3)):
                    args.extend(
                        int(text[pos + i * width : pos + (i + 1) * width])
                        for i in range(n)
                    )
                    pos += n * width + 1
                coefficients = [
                    float(text[a : a + 20] + "e" + text[a + 21 : a + 24])
                    for a in (68, 92)
                ]
                if iv == 2 and power == 1 and rank == 1:
                    removed.append(dict(args=args, coefficients=coefficients))
                    continue
                a = b = 0.0
                for j in range(17):
                    a += args[j] * CI0[j]
                    b += args[j] * CI1[j]
                if len(args) != 17 or not all(
                    math.isfinite(x) for x in (a, b, *coefficients)
                ):
                    raise ValueError("Invalid VSOP2013 arguments or coefficients")
                terms.append((iv - 1, power, a, b, *coefficients))
    if len(removed) != 1 or len(terms) != 294425:
        raise ValueError("Unexpected complete VSOP2013 EMB term count")
    with output.open("xb") as packed:
        packed.write(struct.pack("<I", len(terms)))
        for term in terms:
            packed.write(struct.pack("<IIdddd", *term))
    return dict(
        original_terms=sum(r[2] for r in series),
        evaluated_terms=len(terms),
        removed_original_secular_term=removed,
        series=series,
        amplitude_truncation=None,
        packed_sha256=_sha(output),
    )


def _prepare_sources(
    profile: dict[str, Any], upstream: Path, target: Path
) -> dict[str, Any]:
    target.mkdir()
    expected = profile["native_source_files_sha256"]
    with tarfile.open(upstream / "pyswisseph-2.10.3.2.tar.gz") as archive:
        for member in archive:
            parts = Path(member.name).parts
            if (
                not member.isfile()
                or len(parts) != 3
                or parts[1] != "libswe"
                or parts[2] not in expected
            ):
                continue
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Pinned native source member unavailable")
            with source:
                data = source.read()
            if hashlib.sha256(data).hexdigest() != expected[parts[2]]:
                raise ValueError("Pinned native source member differs")
            with (target / parts[2]).open("xb") as stream:
                stream.write(data)
    if any(not (target / name).is_file() for name in expected):
        raise ValueError("Pinned native source archive is incomplete")
    original = (target / "swemplan.c").read_text()
    needle = "int swi_moshplan2 (double J, int iplm, double *pobj)"
    if original.count(needle) != 1:
        raise ValueError("Unexpected pinned Moshier dispatch")
    patched = original.replace(
        needle,
        "extern int fatebridge_vsop2013_native_emb(double, double *);\n\n" + needle,
    )
    needle = "  const struct plantbl *plan = planets[iplm];"
    if patched.count(needle) != 1:
        raise ValueError("Unexpected pinned Moshier Earth selector")
    patched = patched.replace(
        needle,
        needle + "\n\n  if (iplm == 2) return fatebridge_vsop2013_native_emb(J, pobj);",
    )
    # The stock series always returned OK. The replacement can fail, so every
    # position and finite-difference call must propagate its error before the
    # native pipeline consumes a partial vector or publishes a cached epoch.
    for arguments in (
        "tjd, pnoint2msh[SEI_EMB], xe",
        "tjd - PLAN_SPEED_INTV, pnoint2msh[SEI_EMB], x2",
        "tjd, iplm, xp",
        "tjd - dt, iplm, x2",
    ):
        call = f"swi_moshplan2({arguments});"
        if patched.count(call) != 1:
            raise ValueError("Unexpected pinned native planet call")
        patched = patched.replace(
            call, f"if (swi_moshplan2({arguments}) != OK) return ERR;"
        )
    needle = "static void embofs_mosh(double tjd, double *xemb) \n{"
    if patched.count(needle) != 1:
        raise ValueError("Unexpected pinned lunar offset")
    patched = patched.replace(needle, needle + profile["lunar_replacement_c"])
    (target / "swemplan-vsop2013.c").write_text(patched)
    package = files("fatebridge").joinpath("data/astronomy/vsop2013")
    for name in ("vsop_emb.c", "native_bridge.c", "embedded_series.S"):
        (target / name).write_bytes(package.joinpath(name).read_bytes())
    api = package.joinpath("native_api.c.in").read_text()
    for key, value in zip(
        ("@WORKING_LOW@", "@WORKING_HIGH@"), profile["working_jd_tt"]
    ):
        api = api.replace(key, repr(float(value)))
    (target / "native_api.c").write_text(api)
    for name in ("dtdb.c", "erfa.h", "erfam.h"):
        shutil.copyfile(upstream / name, target / name)
    parsed = _pack_series(upstream / "VSOP2013p3.dat", target / "emb-series.bin")
    if parsed["packed_sha256"] != profile["embedded_series_sha256"]:
        raise ValueError("Series parser differs from frozen independent packed bytes")
    return parsed


def build(
    output: Path,
    *,
    source_dir: Path | None = None,
    compiler: str | None = None,
    linker: str | None = None,
) -> dict[str, Any]:
    system = platform.system()
    if system not in {"Darwin", "Linux"} or sys.byteorder != "little":
        raise ValueError(
            "VSOP2013 builder currently requires macOS/Linux little-endian"
        )
    profile, profile_sha = source_profile()
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    upstream, source = output / "upstream", output / "source"
    _acquire(profile["sources"], upstream, source_dir)
    parsed = _prepare_sources(profile, upstream, source)
    observed = {
        name: _sha(source / name) for name in profile["calculation_files_sha256"]
    }
    graph_sha = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        observed != profile["calculation_files_sha256"]
        or graph_sha != profile["calculation_source_sha256"]
    ):
        raise ValueError("Build sources differ from the qualified VSOP2013 graph")
    marker = f"""#define FB_API __attribute__((visibility("default")))
FB_API const char *fatebridge_vsop2013_model_id(void) {{ return "{MODEL_ID}"; }}
FB_API const char *fatebridge_vsop2013_profile_sha256(void) {{ return "{profile_sha}"; }}
FB_API int fatebridge_vsop2013_abi_version(void) {{ return 1; }}
"""
    (source / "model_marker.c").write_text(marker)
    compiler = compiler or shutil.which("cc")
    if not compiler:
        raise ValueError("A C compiler is required for the optional VSOP2013 library")
    library = output / (
        "vsop2013-solar.dylib" if system == "Darwin" else "vsop2013-solar.so"
    )
    flags = (
        [
            "-dynamiclib",
            "-isysroot",
            "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
        ]
        if system == "Darwin"
        else ["-shared", "-fPIC", "-Wl,-Bsymbolic"]
    )
    if linker:
        flags.append("-fuse-ld=" + linker)
    command = [
        compiler,
        *flags,
        "-std=gnu99",
        "-fsigned-char",
        "-O2",
        "-fno-fast-math",
        "-ffp-contract=off",
        "-fvisibility=hidden",
        "-I",
        str(source),
        *CORE,
        "vsop_emb.c",
        "native_bridge.c",
        "native_api.c",
        "dtdb.c",
        "embedded_series.S",
        "model_marker.c",
        "-lm",
        "-o",
        str(library),
    ]
    with (output / "build-console.txt").open("x") as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=log)
    record = dict(
        command=command,
        returncode=result.returncode,
        calculation_files_sha256=observed,
        source_profile_sha256=profile_sha,
        calculation_source_sha256=graph_sha,
        parsing=parsed,
        embedded_coefficients=True,
        exported_api="checked Sun only",
        erfa_runtime_dependency="compiled into this binary",
    )
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    if result.returncode:
        raise RuntimeError(
            "VSOP2013 compilation failed; original sources and log retained"
        )
    probe = ctypes.CDLL(str(library))
    for symbol, expected_value in (
        ("fatebridge_vsop2013_model_id", MODEL_ID),
        ("fatebridge_vsop2013_profile_sha256", profile_sha),
    ):
        method = getattr(probe, symbol)
        method.restype = ctypes.c_char_p
        if method().decode("ascii") != expected_value:
            raise ValueError("Built VSOP2013 identity marker mismatch")
    probe.fatebridge_vsop2013_solar.argtypes = [
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_char_p,
    ]
    probe.fatebridge_vsop2013_solar.restype = ctypes.c_int
    values = (ctypes.c_double * 6)()
    error = ctypes.create_string_buffer(1024)
    before = probe.fatebridge_vsop2013_solar(2451545.0, values, error)
    if (
        before != -1
        or error.value != b"vsop2013_not_initialized"
        or any(math.isfinite(x) for x in values)
    ):
        raise ValueError(
            "New VSOP2013 library does not reject an uninitialized calculation"
        )
    probe.fatebridge_vsop2013_initialize.argtypes = []
    probe.fatebridge_vsop2013_initialize.restype = ctypes.c_int
    if probe.fatebridge_vsop2013_initialize() != 0:
        raise ValueError("Built VSOP2013 immutable series could not be initialized")
    after = probe.fatebridge_vsop2013_solar(2451545.0, values, error)
    if after != 260 or not all(math.isfinite(x) for x in values):
        raise ValueError("Built VSOP2013 initialized calculation failed")
    (output / "probe.json").write_text(
        json.dumps(
            dict(
                uninitialized_returncode=before,
                uninitialized_finite_coordinates=0,
                initialized_return_flags=after,
                initialized_coordinates=list(values),
            ),
            indent=2,
        )
        + "\n"
    )
    manifest = dict(
        model_id=MODEL_ID,
        version=profile["version"],
        abi_version=1,
        source_profile_sha256=profile_sha,
        calculation_source_sha256=graph_sha,
        binary=library.name,
        binary_sha256=_sha(library),
        system=system,
        machine=platform.machine(),
        build_record="build.json",
        embedded_series_sha256=profile["embedded_series_sha256"],
        source_url=profile["reference"],
        source_identity_scope="Local pinned-source build and actual image identity; not an upstream signature or all-epoch physical/civil certification",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--compiler")
    parser.add_argument("--linker")
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.output,
                source_dir=args.source_dir,
                compiler=args.compiler,
                linker=args.linker,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
