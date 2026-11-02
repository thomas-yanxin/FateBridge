"""Explicit v61 source evolution; all original and v60 references stay immutable."""

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_source_evolution_v61"
MANIFEST_SHA256 = "0473f7604de45bd74769a928fc2887ba18eaae4d641ff074a23d2c671e484b8c"
PREVIOUS_FOLDER = Path(__file__).parent / "fixtures/meihua_source_evolution_v60"
PREVIOUS_MANIFEST_SHA256 = (
    "deb6577785b405d8d8275ab0eceb20d74b219e3e26c21fb33520559e7a8c64cc"
)


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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate evolution JSON key")
        result[key] = value
    return result


def load_json(raw):
    def nonfinite(value):
        raise ValueError("Non-finite evolution JSON value: " + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def assert_fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Source evolution manifest changed")
    manifest = load_json(raw)
    require(
        manifest["original_history_reference_rewritten"] is False
        and manifest["previous_v60_reference_rewritten"] is False,
        "Earlier references cannot be rewritten",
    )
    for name, digest in manifest["files"].items():
        require(
            sha((FOLDER / name).read_bytes()) == digest,
            "Source evolution reference changed: " + name,
        )
    raw = (PREVIOUS_FOLDER / "manifest.json").read_bytes()
    require(
        sha(raw) == PREVIOUS_MANIFEST_SHA256,
        "Previous source evolution manifest changed",
    )
    for name, digest in load_json(raw)["files"].items():
        require(
            sha((PREVIOUS_FOLDER / name).read_bytes()) == digest,
            "Previous source evolution reference changed: " + name,
        )
    return manifest


class StripChapters(ast.NodeTransformer):
    def __init__(self, names, modules, restore_old_error):
        self.names = names
        self.modules = modules
        self.restore_old_error = restore_old_error

    def visit_ImportFrom(self, node):
        return None if node.module in self.modules else node

    def visit_If(self, node):
        if any(
            ast.dump(node.test)
            == ast.dump(ast.parse("topic == " + name, mode="eval").body)
            for name in self.names
        ):
            return None
        return self.generic_visit(node)

    def visit_Tuple(self, node):
        node.elts = [
            x
            for x in node.elts
            if not isinstance(x, ast.Name) or x.id not in self.names
        ]
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if (
            self.restore_old_error
            and node.value == "Select one of the published Meihua topic chapters"
        ):
            node.value = "Select one of the ten published Meihua topic chapters"
        return node


def normalize_request(current, original, removed):
    old_class = next(
        n
        for n in original.body
        if isinstance(n, ast.ClassDef) and n.name == "MeihuaInterpretationOptions"
    )
    new_class = next(
        n
        for n in current.body
        if isinstance(n, ast.ClassDef) and n.name == "MeihuaInterpretationOptions"
    )
    old_fields = {
        n.target.id: n
        for n in old_class.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    for node in new_class.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if name == "interpretation_topic":
            require(
                isinstance(node.annotation, ast.Subscript)
                and isinstance(node.annotation.slice, ast.Tuple),
                "Unknown topic annotation",
            )
            node.annotation.slice.elts = [
                n
                for n in node.annotation.slice.elts
                if not isinstance(n, ast.Constant) or n.value not in removed
            ]
        if name in {"interpretation_topic", "external_observations"}:
            old = next(
                k.value
                for k in old_fields[name].value.keywords
                if k.arg == "description"
            )
            for keyword in node.value.keywords:
                if keyword.arg == "description":
                    keyword.value = deepcopy(old)
    return current


def assert_only_declared_topic_extensions(root):
    for phase in ["original", "previous"]:
        all_new = phase == "original"
        names = {"MARRIAGE_TOPIC", "DINING_TOPIC"} if all_new else {"DINING_TOPIC"}
        modules = {"meihua_marriage", "meihua_dining"} if all_new else {"meihua_dining"}
        original = ast.parse((FOLDER / f"{phase}-meihua_topics.py").read_bytes())
        current = StripChapters(names, modules, all_new).visit(
            ast.parse((root / "core/meihua_topics.py").read_bytes())
        )
        require(
            ast.dump(current) == ast.dump(original),
            "Old topic AST changed outside declared chapter dispatch: " + phase,
        )
        original = ast.parse((FOLDER / f"{phase}-meihua-request.py").read_bytes())
        current = normalize_request(
            ast.parse((root / "core/requests/meihua.py").read_bytes()),
            original,
            {"marriage", "dining"} if all_new else {"dining"},
        )
        require(
            ast.dump(current) == ast.dump(original),
            "Old request AST changed outside declared enum and two descriptions: "
            + phase,
        )


@lru_cache(maxsize=1)
def _load():
    assert_fingerprints()
    binding = load_json((FOLDER / "binding.json").read_bytes())
    require(
        binding["id"] == "meihua_reviewed_source_evolution_v61",
        "Unknown source evolution",
    )
    require(
        binding["phase"]
        == "after_dining_production_and_all_18577_unchanged_native_receipts_before_history_guard_migration",
        "Wrong source evolution phase",
    )
    require(
        binding["previous_evolution_manifest_sha256"] == PREVIOUS_MANIFEST_SHA256,
        "Previous source reference changed",
    )
    require(
        binding["old_source_guard_without_transition_passed"] is False,
        "Do not relabel original source guard",
    )
    require(
        binding["original_historical_raw_hash_gate_passed"] is False,
        "Do not relabel raw hash gate",
    )
    require(
        binding["independent_source_or_prediction_truth"] is False,
        "Engineering transition is not an oracle",
    )
    require(
        set(binding["replaced_complete_source_guards"])
        == {"core/meihua_topics.py", "core/requests/meihua.py"},
        "Unexpected source transition scope",
    )
    require(
        binding["replaced_named_ast_guards"] == {},
        "Shared named AST guards cannot change here",
    )
    require(
        set(binding["additional_complete_source_guards"])
        == {
            "core/meihua_marriage.py",
            "data/meihua/marriage-nlc1925-v1.json",
            "core/meihua_dining.py",
            "data/meihua/dining-nlc1925-v1.json",
        },
        "Unexpected new source scope",
    )
    previous = load_json((PREVIOUS_FOLDER / "binding.json").read_bytes())
    require(
        binding["previous_additional_complete_source_guards"]
        == previous["additional_complete_source_guards"],
        "Previous additional guard set changed",
    )
    for name, digest in previous["additional_complete_source_guards"].items():
        require(
            binding["additional_complete_source_guards"][name] == digest,
            "Previous marriage source changed",
        )
    for topic in ["marriage", "dining"]:
        require(
            binding["additional_complete_source_guards"][
                f"data/meihua/{topic}-nlc1925-v1.json"
            ]
            == binding[f"preimplementation_{topic}_profile_sha256"],
            "Profile changed from preimplementation reference",
        )
    before = load_json(
        gzip.decompress((FOLDER / "native-before.json.gz").read_bytes())
    )["rows"]
    after = load_json(gzip.decompress((FOLDER / "native-after.json.gz").read_bytes()))
    require(
        len(before) == len(after) == binding["native_receipt_rows"] == 18577,
        "Native queue shrunk",
    )
    require(
        binding["original_native_receipt_rows"] == 13546
        and binding["additional_v60_context_rows"] == 5031,
        "Earlier scopes cannot shrink",
    )
    identities = set()
    for i, (old, new) in enumerate(zip(before, after, strict=True)):
        key = canonical({"tool": old["tool"], "arguments": old["arguments"]})
        require(key not in identities, "Duplicate native input identity")
        identities.add(key)
        require(
            old["index"] == new["index"] == i
            and old["tool"] == new["tool"]
            and old["arguments"] == new["arguments"],
            "Native input identity changed",
        )
        require(
            old["sha256"] == new["sha256"] == new["before_sha256"],
            "Native output changed",
        )
    return binding, before


def additional_guarded_source_paths():
    assert_fingerprints()
    from tests.meihua_clock_evolution_reference import additional_source_paths
    from tests.meihua_instant_source_evolution import (
        additional_source_paths as instant_paths,
    )

    return (
        set(_load()[0]["additional_complete_source_guards"])
        | set(additional_source_paths())
        | instant_paths()
    )


def _reviewed_source_guards_v64(data, root):
    assert_fingerprints()
    binding, before = _load()
    require(
        sha(canonical(data["source_guards"]).encode())
        == binding["original_full_guards_sha256"],
        "Original complete source guards changed",
    )
    require(
        sha(canonical(data["named_ast_guards"]).encode())
        == binding["original_named_ast_guards_sha256"],
        "Original named AST guards changed",
    )
    require(len(data["rows"]) == 13546, "Original native queue changed")
    for i, (record, old) in enumerate(zip(data["rows"], before[:13546], strict=True)):
        require(
            record["index"] == i
            and record["tool"] == old["tool"]
            and record["arguments"] == old["arguments"]
            and record["current_sha256"] == old["sha256"],
            "Native receipt no longer binds original history",
        )
    full = deepcopy(data["source_guards"])
    for name, record in binding["replaced_complete_source_guards"].items():
        require(
            full[name]
            == record["before_sha256"]
            == sha((FOLDER / record["original_file"]).read_bytes()),
            "Original source preimage mismatch",
        )
        require(
            record["previous_sha256"]
            == sha((FOLDER / record["previous_file"]).read_bytes()),
            "Previous source preimage mismatch",
        )
        full[name] = record["after_sha256"]
    full.update(binding["additional_complete_source_guards"])
    from tests.meihua_clock_evolution_reference import extend_clock_guards

    full, named = extend_clock_guards(full, deepcopy(data["named_ast_guards"]), root)
    from tests.meihua_instant_source_evolution import extend_instant_guards

    full, named = extend_instant_guards(full, named, root)
    for name, digest in full.items():
        require(
            sha((root / name).read_bytes()) == digest,
            "Listed source file changed: " + name,
        )
    assert_only_declared_topic_extensions(root)
    return full, named


def reviewed_source_guards(data, root):
    from tests.meihua_fractional_source_evolution import reviewed_fractional_guards

    return reviewed_fractional_guards(data, root, _reviewed_source_guards_v64)
