"""Independent observation of accepted native lunation calls, not an astronomy oracle.

Does not import production trace/model parsing. Bind each managed result to an exact raw C calc return, and capture that
return's file slots before any managed wrapper or caller can reset state.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


class NativeSourceWitness:
    def __init__(self, runtime):
        self.runtime = runtime
        self.entries = []
        self.files = {}
        self.paths = {}
        manifest_path = (
            Path(runtime.__file__).resolve().parents[2]
            / "data/astro/ephemeris-manifest-v1.json"
        )
        self.packaged_files = json.loads(manifest_path.read_text())["files"]

    def _context(self, model):
        if model == "moshier":
            return {"model": model, "status": "library_builtin", "file_ids": []}, {}
        ids = []
        files = {}
        for slot in ((0,) if model == "jpl" else (0, 1)):
            name, start, end, de = self.runtime.swe.get_current_file_data(slot)
            if not name:
                continue
            path = Path(name)
            assert path.is_file(), ("native file unavailable at calc return", str(path))
            raw = path.read_bytes() if path not in self.paths else None
            if raw is not None:
                self.paths[path] = hashlib.sha256(raw).hexdigest()
            digest = self.paths[path]
            if model == "jpl":
                if raw is None:
                    raw = path.read_bytes()
                for byte_order in ("<", ">"):
                    if struct.unpack_from(byte_order + "i", raw, 2840)[0] == 441:
                        start, end, _ = struct.unpack_from(byte_order + "3d", raw, 2652)
                        de = 441
                        break
                else:
                    raise AssertionError("Unsupported direct-access JPL header")
            assert math.isfinite(start) and math.isfinite(end) and start < end
            identity = f"{'jpl' if model=='jpl' else 'se1'}:{slot}:{digest}"
            ids.append(identity)
            files[identity] = {
                "id": identity,
                "slot": slot,
                "filename": path.name,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "start_julian_day_tt": float(start),
                "end_julian_day_tt": float(end),
                "de_number": int(de),
                "matches_packaged_manifest": (
                    model == "swieph"
                    and self.packaged_files.get(path.name, {}).get("sha256") == digest
                    and self.packaged_files.get(path.name, {}).get("bytes")
                    == path.stat().st_size
                ),
            }
        assert ids, ("No file context for returned backend", model)
        return {
            "model": model,
            "status": (
                "jpl_context_observed" if model == "jpl" else "se1_contexts_observed"
            ),
            "file_ids": sorted(set(ids)),
        }, files

    @contextmanager
    def observe(self):
        original = self.runtime.ephemeris_call
        swe = self.runtime.swe
        native_calc = swe.calc
        ephemeris_bits = swe.FLG_SWIEPH | swe.FLG_MOSEPH | swe.FLG_JPLEPH
        active = []

        def model_from_flags(flags):
            choices = [
                name
                for bit, name in (
                    (swe.FLG_JPLEPH, "jpl"),
                    (swe.FLG_SWIEPH, "swieph"),
                    (swe.FLG_MOSEPH, "moshier"),
                )
                if flags & bit
            ]
            assert len(choices) == 1, flags
            return choices[0]

        def observed_native(epoch, body, flags=258):
            result = native_calc(epoch, body, flags)
            if active:
                scope = active[-1]
                if (
                    epoch == scope["epoch"]
                    and body == scope["body"]
                    and flags & ~ephemeris_bits == scope["requested"] & ~ephemeris_bits
                ):
                    returned = int(result[1])
                    context, files = self._context(model_from_flags(returned))
                    scope["native_returns"].append(
                        {
                            "coordinates": tuple(result[0]),
                            "returned_flags": returned,
                            "native_requested_flags": int(flags),
                            "context": context,
                            "files": files,
                        }
                    )
            return result

        def watched(operation, *args, **kwargs):
            if operation != "calc" or args[1] not in (swe.SUN, swe.MOON):
                return original(operation, *args, **kwargs)
            requested = int(args[2] if len(args) > 2 else kwargs["flags"])
            frame = bool(requested & swe.FLG_SIDEREAL)
            allowed = swe.FLG_SWIEPH | (swe.FLG_SIDEREAL if frame else swe.FLG_SPEED)
            assert requested == allowed, ("Unclassified luminary calc", requested)
            scope = {
                "epoch": args[0],
                "body": args[1],
                "requested": requested,
                "native_returns": [],
            }
            active.append(scope)
            try:
                result = original(operation, *args, **kwargs)
            finally:
                active.pop()
            matches = [
                r
                for r in scope["native_returns"]
                if r["coordinates"] == tuple(result[0])
                and r["returned_flags"] == result[1]
            ]
            assert matches, "Managed result has no matching observed raw C calc return"
            selected = matches[-1]
            self.files.update(selected["files"])
            self.entries.append(
                {
                    "body": "Sun" if args[1] == swe.SUN else "Moon",
                    "stage": "sidereal_display" if frame else "tropical_search",
                    "epoch_tt": float(args[0]),
                    "requested_flags": requested,
                    "returned_flags": int(result[1]),
                    "native_requested_flags": selected["native_requested_flags"],
                    "matching_raw_native_returns": len(matches),
                    **selected["context"],
                }
            )
            return result

        with (
            patch.object(swe, "calc", observed_native),
            patch.object(self.runtime, "ephemeris_call", watched),
        ):
            yield self
        for path, digest in self.paths.items():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, (
                "Reference input changed",
                str(path),
            )

    def expected(self):
        contexts = {}
        last = {}
        models = {}
        for entry in self.entries:
            body = entry["body"]
            context = {k: entry[k] for k in ("model", "status", "file_ids")}
            last[body] = context
            models.setdefault(body, set()).add(entry["model"])
            key = (
                body,
                entry["stage"],
                entry["model"],
                entry["status"],
                tuple(entry["file_ids"]),
            )
            if key not in contexts:
                contexts[key] = {
                    "body": body,
                    "stage": entry["stage"],
                    **context,
                    "sample_count": 0,
                    "minimum_jd_tt": entry["epoch_tt"],
                    "maximum_jd_tt": entry["epoch_tt"],
                }
            c = contexts[key]
            c["sample_count"] += 1
            c["minimum_jd_tt"] = min(c["minimum_jd_tt"], entry["epoch_tt"])
            c["maximum_jd_tt"] = max(c["maximum_jd_tt"], entry["epoch_tt"])
        return {
            "models_by_body": {k: sorted(v) for k, v in models.items()},
            "models_stable": all(len(v) == 1 for v in models.values()),
            "sample_contexts": list(contexts.values()),
            "by_factor": last,
            "files": [self.files[k] for k in sorted(self.files)],
        }

    def differences(self, result):
        actual = result["ephemeris_source"]
        expected = self.expected()
        differences = []
        for name in ("models_by_body", "models_stable", "sample_contexts"):
            if actual[name] != expected[name]:
                differences.append(name)
        physical = actual["physical_ephemeris_source"]
        if physical["by_factor"] != expected["by_factor"]:
            differences.append("physical_ephemeris_source.by_factor")
        af = [
            {
                k: f[k]
                for k in (
                    "id",
                    "slot",
                    "filename",
                    "sha256",
                    "bytes",
                    "start_julian_day_tt",
                    "end_julian_day_tt",
                    "de_number",
                    "matches_packaged_manifest",
                )
            }
            for f in physical["files"]
        ]
        if af != expected["files"]:
            differences.append("physical_ephemeris_source.files")
        if (
            actual["absolute_accuracy_certified"] is not False
            or physical["accuracy_certified"] is not False
            or physical["atomic_file_read_proven"] is not False
        ):
            differences.append("unjustified_certification")
        return differences

    def assert_matches(self, result):
        differences = self.differences(result)
        assert not differences, (
            "Source receipt differs from immediate native observations",
            differences,
        )
