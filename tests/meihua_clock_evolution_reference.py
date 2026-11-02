"""Reviewed clock provenance evolution, retaining every earlier raw mismatch."""

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from tests.meihua_guard_originals import original_helper

FOLDER = Path(__file__).parent / "fixtures/meihua_clock_evolution_v63"
MANIFEST_SHA256 = "9475236974c71bfcaa4730aa2fd850630f20f5001ef4b3e10308711c65bf4b0c"
INPUT_FOLDER = FOLDER.parent / "meihua_clock_input_v1"
INPUT_MANIFEST_SHA256 = (
    "2e6119a511664b4b6d67c6d677ddc55554eb21f4f7df3df86541ad3a25b569e4"
)
CLOCK_PATHS = [
    "meihua.calendar_policy.civil_clock_resolution",
    "meihua.rule_trace.5.result",
    "calendar_context.lunar_calendar.meihua.calendar_policy.civil_clock_resolution",
    "calendar_context.lunar_calendar.meihua.rule_trace.5.result",
]
ALLOWED = {
    *(p + ".input_components" for p in CLOCK_PATHS),
    *(p + ".clock_label_precision" for p in CLOCK_PATHS),
    "interpretation.evidence_scope.clock_input",
    "summary",
    "interpretation.comprehensive_judgement",
    "interpretation.traditional_judgement",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return sha(canonical(value).encode())


def read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate clock evolution JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Non-finite clock evolution JSON: " + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def fingerprints():
    for folder, expected in [
        (FOLDER, MANIFEST_SHA256),
        (INPUT_FOLDER, INPUT_MANIFEST_SHA256),
    ]:
        raw = (folder / "manifest.json").read_bytes()
        require(sha(raw) == expected, "Clock evolution manifest changed")
        manifest = read_json(raw)
        for name, value in manifest["files"].items():
            require(
                sha((folder / name).read_bytes()) == value,
                "Clock evolution reference changed: " + name,
            )
    from tests import meihua_clock_source_scope as scope

    require(
        sha(original_helper(Path(scope.__file__).name).read_bytes())
        == sha((FOLDER / "reviewed-source-scope.py").read_bytes()),
        "Reviewed clock source-scope helper changed",
    )
    from tests import meihua_second_source_evolution as previous

    previous.fingerprints()


def inverse_clock_delta(value, changes):
    # Service results share clock dictionaries between aliases; JSON receipts do
    # not. Break only Python aliases before applying the exact inverse patches.
    result = read_json(canonical(value))
    for change in changes:
        path = change["path"]
        require(
            ".".join(map(str, path)) in ALLOWED,
            "Clock inverse patch left declared scope",
        )
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        key = path[-1]
        require(
            (
                change["after_present"] and key in parent
                if isinstance(parent, dict)
                else change["after_present"]
            ),
            "Clock inverse lost its after value",
        )
        require(
            canonical(parent[key]) == canonical(change["after"]),
            "Clock inverse after value changed",
        )
        if change["before_present"]:
            parent[key] = deepcopy(change["before"])
        else:
            del parent[key]
    return result


def _lines(path):
    return [read_json(line) for line in gzip.open(path, "rt", encoding="utf-8")]


@lru_cache(maxsize=2)
def _load(folder_key, manifest_key):
    binding = read_json((FOLDER / "binding.json").read_bytes())
    require(
        binding["id"] == "meihua_clock_component_evolution_v63",
        "Unknown clock evolution",
    )
    require(
        binding["phase"]
        == "after_nine_production_files_and_23927_native_receipts_before_source_guard_and_history_migration",
        "Unknown clock migration phase",
    )
    require(
        binding["preimplementation_clock_truth_manifest_sha256"]
        == INPUT_MANIFEST_SHA256
        and binding[
            "data_are_after_production_engineering_receipts_not_independent_truth"
        ]
        is True
        and binding["calendar_algorithms_or_chapter_rules_changed"] is False
        and binding["measurement_uncertainty_interval_inferred"] is False,
        "Clock transition truth scope changed",
    )
    require(
        binding["original_full_raw_hash_gate_passed"] is False
        and not binding["old_native_receipts_rewritten"]
        and binding["new_real_world_observations"] == 0,
        "Do not relabel original gates or observations",
    )
    from tests import meihua_second_source_evolution as previous

    old = previous.load()
    require(
        binding["previous_v62_manifest_sha256"] == previous.MANIFEST_SHA256,
        "Previous clock evolution changed",
    )
    before = read_json(
        gzip.decompress((FOLDER / "native-before.json.gz").read_bytes())
    )["rows"]
    after = read_json(gzip.decompress((FOLDER / "native-after.json.gz").read_bytes()))
    require(
        len(before) == len(after) == binding["native_cases"] == 23927,
        "Clock native queue shrunk",
    )
    prior = read_json(
        gzip.decompress((previous.FOLDER / "native-after.json.gz").read_bytes())
    )
    require(
        len(prior) == binding["original_native_cases"] == 23595,
        "Original clock queue shrunk",
    )
    time_before = {r["index"]: r for r in _lines(FOLDER / "time-before.jsonl.gz")}
    time_after = {r["index"]: r for r in _lines(FOLDER / "time-after.jsonl.gz")}
    transitions = read_json(
        gzip.decompress((FOLDER / "output-transitions.json.gz").read_bytes())
    )
    require(
        len(transitions)
        == len(time_before)
        == len(time_after)
        == binding["clock_transition_rows"]
        == 340,
        "Time input queue shrunk",
    )
    by_index = {r["index"]: r for r in transitions}
    require(len(by_index) == 340, "Duplicate clock transition index")
    identities = set()
    changed = []
    cast_count = 0
    admissions = 0
    full = {}
    for i, (a, z) in enumerate(zip(before, after, strict=True)):
        identity = canonical({"tool": a["tool"], "arguments": a["arguments"]})
        require(identity not in identities, "Duplicate native clock identity")
        identities.add(identity)
        require(
            type(a["index"]) is int
            and a["index"] == z["index"] == i
            and a["tool"] == z["tool"]
            and a["arguments"] == z["arguments"]
            and a["sha256"] == z["before_sha256"],
            "Clock input identity or before receipt changed",
        )
        if i < 23595:
            p = prior[i]
            require(
                p["index"] == i
                and p["tool"] == a["tool"]
                and p["arguments"] == a["arguments"]
                and p["sha256"] == a["sha256"],
                "Previous native receipt rebound",
            )
            if a["sha256"] != z["sha256"]:
                changed.append(i)
        if a["tool"] == "meihua_cast":
            require(a["sha256"] == z["sha256"], "Non-clock production output changed")
            cast_count += 1
            continue
        require(
            a["tool"] == "meihua_analysis" and i in by_index,
            "Unknown native tool identity",
        )
        receipt = by_index[i]
        require(
            receipt["arguments"] == a["arguments"]
            and receipt["before_sha256"] == a["sha256"]
            and receipt["after_sha256"] == z["sha256"],
            "Clock transition receipt changed",
        )
        require(
            time_before[i]["arguments"] == a["arguments"]
            and digest(time_before[i]["before"]) == a["sha256"]
            and time_after[i]["arguments"] == a["arguments"]
            and digest(time_after[i]["after"]) == z["sha256"],
            "Complete clock packet changed",
        )
        clock = time_after[i]["after"]["meihua"]["calendar_policy"][
            "civil_clock_resolution"
        ]["input_components"]
        known = [
            "year",
            "month",
            "day",
            "hour",
            *[
                n
                for n in ["minute", "second"]
                if a["arguments"].get("analysis_" + n) is not None
            ],
        ]
        missing = [n for n in ["minute", "second"] if n not in known]
        require(
            clock["supplied_components"] == known
            and clock["omitted_components"] == missing
            and clock["calculation_defaults"] == {n: 0 for n in missing}
            and clock["provenance"] == "direct_service_optional_components"
            and clock["uncertainty_interval"] is None
            and clock["observed_precision_certified"] is False
            and clock["calendar_stability"] == "not_assessed",
            "Clock packet falsely claimed supplied components or accuracy",
        )
        for edit in receipt["declared_delta"]:
            path = ".".join(map(str, edit["path"]))
            if path in {
                "summary",
                "interpretation.comprehensive_judgement",
                "interpretation.traditional_judgement",
            }:
                require(
                    bool(missing)
                    and edit["after"] == clock["statement"] + " " + edit["before"],
                    "Clock notice replaced an old reading",
                )
        reference = receipt["nominal_reference_before_index"]
        require(reference in time_before, "Nominal reference missing")
        restored = inverse_clock_delta(
            time_after[i]["after"], receipt["declared_delta"]
        )
        require(
            digest(restored)
            == receipt["nominal_reference_before_sha256"]
            == digest(time_before[reference]["before"]),
            "Clock delta changed numerical or undeclared facts",
        )
        if receipt["before_was_error"]:
            admissions += 1
            require(
                a["arguments"].get("analysis_minute", "absent") is None
                and "error" in time_before[i]["before"]
                and "error" not in time_before[reference]["before"],
                "Unknown new input admission",
            )
            require(
                before[reference]["arguments"]
                == {**a["arguments"], "analysis_minute": 0},
                "Null minute reference is not the same nominal clock",
            )
        else:
            require(
                reference == i and digest(restored) == a["sha256"],
                "Valid native before rebound",
            )
        full[identity] = (z["sha256"], receipt)
    require(
        cast_count == binding["original_raw_unchanged"] == 23587
        and changed == binding["original_raw_changed_indices"]
        and len(changed) == 8
        and admissions == binding["new_nullable_minute_admissions"] == 56,
        "Original mismatches or admissions relabelled",
    )
    partials = read_json(
        gzip.decompress((FOLDER / "time-partials12.json.gz").read_bytes())
    )
    require(
        len(partials) == binding["original_partial_time_contexts"] == 12,
        "Original time intermediates shrunk",
    )
    partial_index = {}
    for ordinal, r in enumerate(partials):
        require(
            r["original_index"] == ordinal
            and r["native_index"] in time_before
            and r["arguments"] == before[r["native_index"]]["arguments"],
            "Time intermediate identity changed",
        )
        require(
            digest(r["before"]) == r["before_sha256"]
            and digest(r["after"]) == r["after_sha256"]
            and digest(inverse_clock_delta(r["after"], r["delta"]))
            == r["before_sha256"],
            "Complete time intermediate changed",
        )
        require(r["after_sha256"] not in partial_index, "Duplicate time intermediate")
        partial_index[r["after_sha256"]] = r
    require(
        binding["clock_full_file_before_sha256"]
        == old["full_source_transition"]["after_sha256"],
        "Previous clock preimage changed",
    )
    return {"binding": binding, "full": full, "partial": partial_index}


def load():
    fingerprints()
    return _load(str(FOLDER.resolve()), MANIFEST_SHA256)


def additional_source_paths():
    data = load()["binding"]
    return set(data["seven_modified_module_ast_scope"]) | set(
        data["additional_complete_source_guards"]
    )


def _member_hash(path, name):
    node = next(
        n for n in ast.parse(path.read_bytes()).body if getattr(n, "name", None) == name
    )
    return sha(ast.dump(node, include_attributes=False).encode())


def extend_clock_guards(full, named, root):
    initial = load()["binding"]
    from tests import meihua_clock_integration_reference as integration
    from tests import meihua_second_source_evolution as previous
    from tests.meihua_clock_source_scope import assert_clock_source_scope

    data = integration.source_policy(initial)
    previous.fingerprints()
    prior = read_json((previous.FOLDER / "binding.json").read_bytes())
    require(
        full["core/meihua_clock.py"]
        == prior["full_source_transition"]["before_sha256"],
        "Original complete clock guard changed",
    )
    full["core/meihua_clock.py"] = data["clock_full_file_after_sha256"]
    for path, members in prior["named_ast_transitions"].items():
        for name, entry in members.items():
            require(
                named[path][name] == entry["before_sha256"],
                "Original named clock guard changed",
            )
            before_name = initial["seven_modified_module_ast_scope"][path][
                "before_file"
            ]
            require(
                _member_hash(INPUT_FOLDER / before_name, name) == entry["after_sha256"],
                "Previous named clock preimage changed",
            )
    for path, members in prior["new_named_ast_guards"].items():
        require(path not in named, "Previous request guard overwrote old members")
        before_name = initial["seven_modified_module_ast_scope"][path]["before_file"]
        require(
            all(
                _member_hash(INPUT_FOLDER / before_name, n) == h
                for n, h in members.items()
            ),
            "Previous request preimage changed",
        )
        named[path] = deepcopy(members)
    for path, members in data["changed_named_ast_guards"].items():
        require(path in named, "Changed named clock scope unbound")
        require(
            set(members)
            == (
                {"calculate_meihua_analysis"}
                if path == "services/divination.py"
                else {"MeihuaAnalysisRequest"}
            ),
            "Unexpected changed named scope",
        )
        named[path].update(members)
    require(
        set(data["changed_named_ast_guards"])
        == {"services/divination.py", "core/requests/divination.py"},
        "Changed named scope widened",
    )
    for path, members in data["additional_named_ast_guards"].items():
        for name, h in members.items():
            require(
                name not in named.get(path, {}),
                "Additional named guard replaced old scope",
            )
            named.setdefault(path, {})[name] = h
    require(
        set(data["additional_complete_source_guards"])
        == {"core/meihua_clock_input.py", "application/meihua_clock_binding.py"},
        "New complete source scope changed",
    )
    full.update(data["additional_complete_source_guards"])
    require(
        len(full) == 120 and sum(len(v) for v in named.values()) == 29,
        "Clock source guard scope changed",
    )
    for path, members in named.items():
        # Existing history also checks these old shared members, including Assign nodes.
        if (
            path not in data["changed_named_ast_guards"]
            and path not in data["additional_named_ast_guards"]
        ):
            continue
        for name, h in members.items():
            require(
                _member_hash(root / path, name) == h,
                "Named shared AST changed: " + path + ":" + name,
            )
    require(
        set(data["seven_modified_module_ast_scope"])
        == {
            "core/meihua_clock.py",
            "core/requests/divination.py",
            "services/divination.py",
            "services/catalog/divination.py",
            "transports/mcp.py",
            "services/replay_metadata.py",
            "application/execution.py",
        },
        "Modified source module scope changed",
    )
    for path, entry in data["seven_modified_module_ast_scope"].items():
        before = integration.FOLDER / entry["before_file"]
        require(
            sha(before.read_bytes()) == entry["before_sha256"],
            "Clock source preimage bytes changed",
        )
        require(
            sha(
                ast.dump(
                    ast.parse(before.read_bytes()), include_attributes=False
                ).encode()
            )
            == entry["before_module_ast_sha256"],
            "Clock source preimage AST changed",
        )
        require(
            sha(
                ast.dump(
                    ast.parse((root / path).read_bytes()), include_attributes=False
                ).encode()
            )
            == entry["after_module_ast_sha256"],
            "Shared module AST changed: " + path,
        )
    assert_clock_source_scope(root, integration.scope_before_folder())
    return full, named


def restore_clock_before_native(result, arguments):
    data = load()
    identity = canonical({"tool": "meihua_analysis", "arguments": arguments})
    require(identity in data["full"], "Unknown clock input; no historical projection")
    expected, receipt = data["full"][identity]
    require(
        digest(result) == expected,
        "Native current clock output differs from reviewed receipt",
    )
    require(
        not receipt["before_was_error"],
        "Newly admitted null minute has no old success packet",
    )
    restored = inverse_clock_delta(result, receipt["declared_delta"])
    require(
        digest(restored) == receipt["before_sha256"],
        "Clock historical projection changed an undeclared fact",
    )
    return restored


def restore_clock_before_partial(result):
    data = load()
    key = digest(result)
    require(
        key in data["partial"],
        "Current time intermediate differs from reviewed complete clock receipt",
    )
    entry = data["partial"][key]
    restored = inverse_clock_delta(result, entry["delta"])
    require(
        digest(restored) == entry["before_sha256"],
        "Time clock projection changed an undeclared fact",
    )
    return restored
