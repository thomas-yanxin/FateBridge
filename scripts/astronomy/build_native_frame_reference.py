"""Generate native frame controls from the unmodified author C implementation.

The external source checkout and compiler are explicit inputs. This generator
does not import FateBridge or recover a frame by inverting planet positions.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SOURCE_COMMIT = "696bda432298d482d27e67a0cf1238920301a7dd"
SOURCE_FILES: dict[str, str] = {
    "swecl.c": "ab46bdc303978523c69d814d236432541ff48cb410b756ef78cc1e8d2b2be303",
    "swedate.c": "6790e989a003cb6422080d9aecf3c6567a25030f5b5647fd749e5b16422cfac7",
    "swedate.h": "886b001815561f2c5f5e40418ce00d62377cb8962180c38062ac83bfdab77b38",
    "swedll.h": "8bfe26da8ddab988bf4980828da231f6b8608158606b679ce7f68ee44cf692ad",
    "sweephe4.h": "2cab6af5381da9bb7cb08644577b71c7dd9e3a0e69a7080a659d30817448f7b1",
    "swehel.c": "7b4be28627afd22b059389abc4ef679b7259a0bcb9d0510e7ca3825901754b93",
    "swehouse.c": "384c1d7b2a8bcef9f2cf16f7fbf02e7aa18f372bc11320874a5543b92aed95d9",
    "swehouse.h": "7a91a007a4de0900ed6d234d74da421b2372d245b09a2ba8b74d6e2e054a200c",
    "swejpl.c": "44014e260ae9ab2b1e8f413bb8a35fa270e369e3fb4907cd137ae103d2a8d0c2",
    "swejpl.h": "f61ae6173b150f456540afba68500989c642506822e0397cf99c2cb7f50aac0d",
    "swemmoon.c": "1d5f5ef9a95cf9a2f395b6334a58c63851ce0512d65bf08e49d3caf0a9fecb00",
    "swemplan.c": "d13502ca7b92e3e32317b67ba7f012d92fabd1d358c3394c094d5515a3567caa",
    "swemptab.h": "dc7595b81bd49e86a6204ed1e0a041c410a9de5c068fd1d90d350a82d604fb85",
    "swenut2000a.h": "83b0a2f569174b56c8e26971b00f85f5ae52265b34c1c53436c7122e0f1faad7",
    "sweodef.h": "a2ace0fc0ea81ffbf9eb0a7f9fc1c1446d98f07d3a170a2c54b8ef4908325462",
    "sweph.c": "80761ccfae7cd7207a33559d8898b9c5386cced609cfaebbbbf050f7a80ddc4f",
    "sweph.h": "8e44b9c00d23a0b583581f17fc6798ea376649d2517abbb556ee1b1aff6a138a",
    "swephexp.h": "dd8e74e2853915a316041397f31730219b7910333be6bba3934fd77130335f22",
    "swephlib.c": "d41eb2f396163fedd574749de02a25e8547b4e1e4c66783d47ccc0c7e4885a05",
    "swephlib.h": "29a151bb0c6adcb73fa73eff805b498c26bdffbb81e82d55e1b50f79218ea82a",
    "swevents.h": "82ce992f909854f7816386aaaf52f52826c315d5c926172195b57edbe32364e0",
}
WRAPPER = r"""
#include "sweph.c"
#define API __attribute__((visibility("default")))
API int reference_native_frame(double epoch, int sidereal, const char *empty,
    double *angles, double *ayanamsa, double *matrix, char *error) {
  int axis, row, ret;
  int32 flags = SEFLG_MOSEPH;
  double seed[6];
  swe_close();
  swe_set_ephe_path(empty);
  swe_set_sid_mode(SE_SIDM_LAHIRI, 0., 0.);
  ret = swe_calc(epoch, SE_ECL_NUT, SEFLG_MOSEPH, angles, error);
  if (ret < 0) return ret;
  *ayanamsa = 0.;
  if (sidereal) {
    ret = swe_get_ayanamsa_ex(epoch, SEFLG_MOSEPH | SEFLG_NONUT, ayanamsa, error);
    if (ret < 0) return ret;
    flags |= SEFLG_SIDEREAL | SEFLG_NONUT;
  }
  ret = swe_calc(epoch, SE_SUN, flags, seed, error);
  if (ret < 0) return ret;
  for (axis = 0; axis < 3; axis++) {
    struct plan_data p;
    double v[6] = {0,0,0,0,0,0}, saved[6] = {0,0,0,0,0,0};
    memset(&p, 0, sizeof(p));
    p.teval = epoch;
    v[axis] = 1.;
    if (swi_get_denum(SEI_MERCURY, flags) >= 403)
      swi_bias(v, epoch, flags, FALSE);
    for (row = 0; row < 6; row++) saved[row] = v[row];
    swi_precess(v, epoch, flags, J2000_TO_J);
    ret = app_pos_rest(&p, flags, v, saved, &swed.oec, error);
    if (ret < 0) return ret;
    for (row = 0; row < 3; row++) matrix[row*3+axis] = p.xreturn[6+row];
  }
  return 0;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, required=True)
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--sysroot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_directory.resolve()
    source_hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }
    if source_hashes != SOURCE_FILES:
        raise ValueError("Author source files differ from the pinned commit")
    plan = json.loads(args.cases_file.read_text())
    units = (
        "swedate.c",
        "swehouse.c",
        "swejpl.c",
        "swemplan.c",
        "swemmoon.c",
        "swephlib.c",
        "swecl.c",
        "swehel.c",
    )
    rows = []
    with TemporaryDirectory(prefix="fatebridge-native-frame-reference-") as tmp:
        work = Path(tmp)
        wrapper = work / "frame_reference.c"
        wrapper.write_text(WRAPPER)
        library_path = work / (
            "frame_reference.dylib"
            if sys.platform == "darwin"
            else "frame_reference.so"
        )
        empty = work / "empty-ephemeris"
        empty.mkdir()
        command = [
            args.compiler,
            *(["-dynamiclib"] if sys.platform == "darwin" else ["-shared", "-fPIC"]),
        ]
        if args.sysroot is not None:
            command.extend(["-isysroot", str(args.sysroot)])
        command.extend(
            [
                "-fuse-ld=lld",
                "-std=gnu89",
                "-fsigned-char",
                "-O2",
                "-fno-fast-math",
                "-ffp-contract=off",
                "-fvisibility=hidden",
                "-I",
                str(source),
                *(str(source / name) for name in units),
                str(wrapper),
                "-lm",
                "-o",
                str(library_path),
            ]
        )
        subprocess.run(command, check=True)
        library = ctypes.CDLL(str(library_path))
        function = library.reference_native_frame
        pointer = ctypes.POINTER(ctypes.c_double)
        function.argtypes = [
            ctypes.c_double,
            ctypes.c_int,
            ctypes.c_char_p,
            pointer,
            pointer,
            pointer,
            ctypes.c_char_p,
        ]
        function.restype = ctypes.c_int
        for epoch in plan["epochs"]:
            for frame in plan["frames"]:
                angles = (ctypes.c_double * 6)()
                ayanamsa = ctypes.c_double()
                matrix = (ctypes.c_double * 9)()
                error = ctypes.create_string_buffer(1024)
                status = function(
                    epoch,
                    int(frame == "lahiri"),
                    str(empty).encode(),
                    angles,
                    ctypes.byref(ayanamsa),
                    matrix,
                    error,
                )
                if status < 0:
                    raise RuntimeError((epoch, frame, error.value.decode()))
                rows.append(
                    {
                        "jd_tt": epoch,
                        "frame": frame,
                        "ECL_NUT_degrees": list(angles[:4]),
                        "mean_Lahiri_ayanamsa_degrees": (
                            ayanamsa.value if frame == "lahiri" else None
                        ),
                        "original_C_ICRS_to_display_matrix": [
                            list(matrix[3 * i : 3 * i + 3]) for i in range(3)
                        ],
                    }
                )
        library_hash = hashlib.sha256(library_path.read_bytes()).hexdigest()
    reference = {
        "production_imported": False,
        "source_commit": SOURCE_COMMIT,
        "source_url": f"https://github.com/astrorigin/swisseph/tree/{SOURCE_COMMIT}",
        "source_files_sha256": source_hashes,
        "reference_kind": "Original author C frame operations on Cartesian unit axes",
        "coordinate_model_gate": "1e-10",
        "physical_accuracy_or_continuous_domain_certified": False,
        "case_plan": plan,
        "case_plan_sha256": hashlib.sha256(args.cases_file.read_bytes()).hexdigest(),
        "wrapper_source": WRAPPER,
        "wrapper_sha256": hashlib.sha256(WRAPPER.encode()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "compiler_version": subprocess.check_output(
            [args.compiler, "--version"], text=True
        ),
        "reference_library_sha256": library_hash,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
