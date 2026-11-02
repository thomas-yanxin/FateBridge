"""Explicit clock input extension; previous guards and negative receipts stay frozen."""

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_second_source_evolution_v62"
MANIFEST_SHA256 = "d1941147afbd00aab0d75f74cd8132363c5ee5a28e14527f7e84b3cbe99da09d"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Second input transition manifest changed")
    manifest = json.loads(raw)
    require(not manifest["old_references_rewritten"], "Old reference rewritten")
    for name, digest in manifest["files"].items():
        require(
            sha((FOLDER / name).read_bytes()) == digest,
            "Second input reference changed: " + name,
        )


def dump(node):
    return ast.dump(node, include_attributes=False)


def member(path, name):
    return next(
        n for n in ast.parse(path.read_bytes()).body if getattr(n, "name", None) == name
    )


def remove_second_argument(current, original, name):
    i = next(i for i, n in enumerate(current.args.kwonlyargs) if n.arg == name)
    current.args.kwonlyargs.pop(i)
    current.args.kw_defaults.pop(i)
    require(
        dump(current.args) == dump(original.args), "Unrelated clock arguments changed"
    )


def assert_only_declared_seconds_extensions(root):
    old = member(FOLDER / "before-service.py", "calculate_meihua_analysis")
    new = member(root / "services/divination.py", "calculate_meihua_analysis")
    remove_second_argument(new, old, "analysis_second")
    second_validation = ast.parse("""
if analysis_second is not None and (type(analysis_second) is not int or not 0 <= analysis_second <= 59):
    return ParameterError("analysis_second须为已确认的0至59整秒；未知时省略，不支持闰秒标签60。", [{"path": "analysis_second", "code": "invalid_civil_second"}]).as_result()
""").body[0]
    matches = [n for n in new.body if dump(n) == dump(second_validation)]
    require(len(matches) == 1, "Second validation differs from reviewed clause")
    new.body.remove(matches[0])
    datetime_call = next(
        n.value
        for n in new.body
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "analysis_datetime" for t in n.targets
        )
    )
    require(
        len(datetime_call.args) == 6
        and dump(datetime_call.args[-1])
        == dump(
            ast.parse(
                "0 if analysis_second is None else analysis_second", mode="eval"
            ).body
        ),
        "Unexpected second-to-clock expression",
    )
    datetime_call.args.pop()
    calls = [
        n
        for n in ast.walk(new)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "resolve_meihua_clock"
    ]
    require(
        len(calls) == 1 and len(calls[0].keywords) == 1,
        "Unexpected clock resolver call",
    )
    require(
        dump(calls[0].keywords[0])
        == dump(
            ast.keyword(
                arg="seconds_supplied",
                value=ast.parse("analysis_second is not None", mode="eval").body,
            )
        ),
        "Unexpected precision flag",
    )
    calls[0].keywords.clear()
    require(dump(new) == dump(old), "Service AST changed outside declared second input")

    old = member(FOLDER / "before-request.py", "MeihuaAnalysisRequest")
    new = member(root / "core/requests/divination.py", "MeihuaAnalysisRequest")
    fields = [
        n
        for n in new.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "analysis_second"
    ]
    require(len(fields) == 1, "Second request field missing or duplicated")
    new.body.remove(fields[0])
    require(dump(new) == dump(old), "Request AST changed outside added second field")

    old_tree = ast.parse((FOLDER / "before-meihua_clock.py").read_bytes())
    new_tree = ast.parse((root / "core/meihua_clock.py").read_bytes())
    old = next(
        n for n in old_tree.body if getattr(n, "name", None) == "resolve_meihua_clock"
    )
    new = next(
        n for n in new_tree.body if getattr(n, "name", None) == "resolve_meihua_clock"
    )
    remove_second_argument(new, old, "seconds_supplied")
    old_dict = next(n.value.elts[1] for n in old.body if isinstance(n, ast.Return))
    new_dict = next(n.value.elts[1] for n in new.body if isinstance(n, ast.Return))
    extra = [i for i, key in enumerate(new_dict.keys) if key is None]
    require(len(extra) == 1, "Unexpected clock metadata expansion")
    i = extra[0]
    value = new_dict.values[i]
    require(
        isinstance(value, ast.IfExp)
        and dump(value.test) == dump(ast.Name(id="seconds_supplied", ctx=ast.Load()))
        and isinstance(value.body, ast.Dict)
        and [k.value for k in value.body.keys] == ["input_second"],
        "Unknown second metadata component",
    )
    new_dict.keys.pop(i)
    new_dict.values.pop(i)
    i = next(
        i
        for i, key in enumerate(new_dict.keys)
        if isinstance(key, ast.Constant) and key.value == "clock_label_precision"
    )
    require(
        dump(new_dict.values[i])
        == dump(
            ast.parse(
                '"supplied_civil_second; historical_offset_seconds_preserved" if seconds_supplied else "supplied_civil_minute; historical_offset_seconds_preserved"',
                mode="eval",
            ).body
        ),
        "Unexpected clock precision label",
    )
    j = next(
        i for i, key in enumerate(old_dict.keys) if key.value == "clock_label_precision"
    )
    new_dict.values[i] = deepcopy(old_dict.values[j])
    require(
        dump(new_tree) == dump(old_tree),
        "Clock AST changed outside declared precision metadata",
    )


@lru_cache(maxsize=1)
def load():
    fingerprints()
    binding = json.loads((FOLDER / "binding.json").read_bytes())
    require(
        binding["id"] == "meihua_civil_second_source_evolution_v62",
        "Unknown second transition",
    )
    require(
        binding["phase"]
        == "after_three_production_edits_and_23595_unchanged_native_receipts_before_source_guard_migration",
        "Unknown second transition phase",
    )
    require(
        not binding["previous_source_guard_passed"]
        and not binding["original_historical_hash_gate_passed"]
        and not binding["independent_source_or_prediction_truth"]
        and binding["new_independent_prediction_observations"] == 0,
        "Do not relabel earlier negative gates",
    )
    before = json.loads(
        gzip.decompress((FOLDER / "native-before.json.gz").read_bytes())
    )["rows"]
    after = json.loads(gzip.decompress((FOLDER / "native-after.json.gz").read_bytes()))
    require(
        len(before) == len(after) == binding["native_receipt_rows"] == 23595,
        "Second native queue shrunk",
    )
    previous = json.loads(
        gzip.decompress(
            (
                FOLDER.parent / "meihua_source_evolution_v61/native-after.json.gz"
            ).read_bytes()
        )
    )
    require(
        len(previous) == binding["retained_previous_rows"] == 18577
        and binding["additional_v61_dining_rows"] == 5018,
        "Previous native scope shrunk",
    )
    identities = set()
    for i, (a, z) in enumerate(zip(before, after, strict=True)):
        identity = json.dumps(
            {"tool": a["tool"], "arguments": a["arguments"]},
            sort_keys=True,
            ensure_ascii=False,
        )
        require(identity not in identities, "Duplicate second native identity")
        identities.add(identity)
        require(
            a["index"] == z["index"] == i
            and a["tool"] == z["tool"]
            and a["arguments"] == z["arguments"]
            and a["sha256"] == z["sha256"] == z["before_sha256"],
            "Second native receipt changed",
        )
        if i < len(previous):
            p = previous[i]
            require(
                a["index"] == p["index"]
                and a["tool"] == p["tool"]
                and a["arguments"] == p["arguments"]
                and a["sha256"] == p["sha256"],
                "Previous native receipt rebound",
            )
    return binding


def extend_seconds_guards(full, named, root):
    fingerprints()
    binding = load()
    require(
        binding["previous_v61_manifest_sha256"]
        == sha(
            (FOLDER.parent / "meihua_source_evolution_v61/manifest.json").read_bytes()
        ),
        "Previous v61 manifest changed",
    )
    require(
        binding["frozen_boundary_manifest_sha256"]
        == sha((FOLDER.parent / "meihua_input_seconds_v1/manifest.json").read_bytes()),
        "Independent boundary reference changed",
    )
    transition = binding["full_source_transition"]
    require(
        transition["path"] == "core/meihua_clock.py", "Unexpected complete source scope"
    )
    require(
        full[transition["path"]]
        == transition["before_sha256"]
        == sha((FOLDER / "before-meihua_clock.py").read_bytes()),
        "Clock preimage mismatch",
    )
    full[transition["path"]] = transition["after_sha256"]
    require(
        set(binding["named_ast_transitions"]) == {"services/divination.py"}
        and set(binding["named_ast_transitions"]["services/divination.py"])
        == {"calculate_meihua_analysis"},
        "Unexpected named transition scope",
    )
    for path, members in binding["named_ast_transitions"].items():
        for name, record in members.items():
            require(
                named[path][name]
                == record["before_sha256"]
                == sha(dump(member(FOLDER / "before-service.py", name)).encode()),
                "Service preimage mismatch",
            )
            named[path][name] = record["after_sha256"]
    require(
        set(binding["new_named_ast_guards"]) == {"core/requests/divination.py"}
        and set(binding["new_named_ast_guards"]["core/requests/divination.py"])
        == {"MeihuaAnalysisRequest"},
        "Unexpected new named guard scope",
    )
    for path, members in binding["new_named_ast_guards"].items():
        require(path not in named, "New request guard overwrote old scope")
        named[path] = deepcopy(members)
    for path in ["services/divination.py", "core/requests/divination.py"]:
        members = (
            {"calculate_meihua_analysis": named[path]["calculate_meihua_analysis"]}
            if path == "services/divination.py"
            else named[path]
        )
        for name, digest in members.items():
            require(
                sha(dump(member(root / path, name)).encode()) == digest,
                "Named shared AST changed: " + path + ":" + name,
            )
    assert_only_declared_seconds_extensions(root)
    return full, named
