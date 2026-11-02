"""Migrate only declared Ren evidence; preserve original calculations and bytes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / "tests/fixtures/ren_golden_evidence_v1"
CORRECTION = ROOT / "tests/fixtures/ren_golden_expectations_v2"
PINS = {
    "ren_golden_evidence_v1": "c8de2e3d0715d7688de297a72bab909e48f12d501555c6a51f1d83486bacade7",
    "ren_golden_expectations_v2": "ba8420c4ea1ca660bd1906f57ce2ab04d0c033cf187ef5ca9037f7eb9e682667",
}
SLUGS = (
    "api_cn_liureng_gods",
    "api_cn_liureng_runyear",
    "api_cn_jinkou",
    "api_divination_sanshiunited",
)
KEYS = dict(zip(SLUGS, ("liureng_gods", "liureng_runyear", "jinkou", "sanshiunited")))
NEW_LAYERS = {
    "branch_relations",
    "emptiness_evidence",
    "transmission_progression",
    "seasonal_evidence",
    "branch_stars",
    "god_yin",
}
CHAPTER_ADDITIONS = ROOT / "tests/fixtures/jinkou_waseda_golden_v1"
CHAPTER_PIN = "a3d7eea19e1e35335615ca163144a3513ec9519c418986bfd56b24e3aee152c5"
CHAPTER_PATHS = {
    "jinkou.definition_evidence.witnesses.1." + key
    for key in ("full_scan_url", "full_scan_sha256", "chapter_inventory")
}
STRENGTH_ADDITIONS = ROOT / "tests/fixtures/jinkou_waseda_strength_golden_v1"
STRENGTH_PIN = "726a9b84934641595b3b17aabc17775476135094df48b85f696e41fe9017eba4"
STRENGTH_SOURCE_KEYS = ("note", "primary_witness", "witness_difference", "scope")
MONTH_ADDITIONS = ROOT / "tests/fixtures/jinkou_month_building_golden_v1"
MONTH_PIN = "dfba690341bf75ba2e7959b257adc1f3d99657ec0257b5f9401187445315f273"
SELECTION_ADDITIONS = ROOT / "tests/fixtures/liuren_selection_golden_v1"
SELECTION_PIN = "cb96f3e8065b3dc9838d7cc007e345282a7b321b0aadb4db9e9dbef5a30483cc"
NATAL_COURSE_ADDITIONS = ROOT / "tests/fixtures/jinkou_natal_course_golden_v1"
NATAL_COURSE_PIN = "28cf33ffceb9625db2611b9debac0614a26cb80bc850829a3260d8e63ff0dc1f"
NATAL_COURSE_PATHS = {
    "jinkou.natal_course",
    "jinkou.rule_trace",
    "jinkou.ruleset.conventions.natal_course",
    "jinkou.ruleset.version",
    "snapshot_export.section_titles_detected",
    "snapshot_export.sections",
    "snapshot_export.technique.preset_sections",
    "snapshot_export.technique.settings_template.sections",
    "snapshot_export.unknown_detected_sections",
    "snapshot_text",
}
MONTH_KEYS = (
    "month_building_basis",
    "month_building_checks",
    "month_building_pdf_page",
    "month_building_scan_sha256",
    "month_building_scan_url",
    "month_building_scope",
)
MONTH_PATHS = {
    f"{prefix}.{key}"
    for prefix in ("jinkou.qi_evidence", "jinkou.rule_trace.9.result")
    for key in MONTH_KEYS
} | {
    "jinkou.ruleset.conventions.month_building",
    "jinkou.ruleset.version",
    "snapshot_text",
    "snapshot_export.sections.1.content",
}
STRENGTH_SOURCE_PATHS = {
    prefix + "." + key
    for prefix in (
        "jinkou.internal_strength.source_evidence",
        "jinkou.rule_trace.3.result.source_evidence",
    )
    for key in STRENGTH_SOURCE_KEYS
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference() -> dict[str, Any]:
    for folder in (ORIGINALS, CORRECTION):
        if sha(folder / "freeze.json") != PINS[folder.name]:
            raise ValueError("Frozen golden-evidence manifest changed")
        files = json.loads((folder / "freeze.json").read_text())["files"]
        if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"} or any(
            sha(folder / n) != h for n, h in files.items()
        ):
            raise ValueError("Frozen golden-evidence source changed")
    ref: dict[str, Any] = json.loads((CORRECTION / "reference.json").read_text())
    if sha(NATAL_COURSE_ADDITIONS / "freeze.json") != NATAL_COURSE_PIN:
        raise ValueError("Frozen natal-course migration protocol changed")
    natal_files = json.loads((NATAL_COURSE_ADDITIONS / "freeze.json").read_text())[
        "files"
    ]
    if {p.name for p in NATAL_COURSE_ADDITIONS.iterdir()} != set(natal_files) | {
        "freeze.json"
    } or any(sha(NATAL_COURSE_ADDITIONS / n) != d for n, d in natal_files.items()):
        raise ValueError("Frozen natal-course migration inventory changed")
    natal = json.loads((NATAL_COURSE_ADDITIONS / "protocol.json").read_text())
    from scripts.audit_jinkou_natal_course import reference as natal_course_reference

    natal_course_reference()
    if (
        sha(ROOT / "tests/fixtures/jinkou_natal_course_v1/freeze.json")
        != natal["source_reference_sha256"]
        or set(natal["allowed_values"]) != NATAL_COURSE_PATHS
    ):
        raise ValueError("Natal-course migration differs from frozen source and scope")
    ref["natal_course_additions"] = natal["allowed_values"]
    if sha(SELECTION_ADDITIONS / "freeze.json") != SELECTION_PIN:
        raise ValueError("Frozen selection-evidence migration changed")
    selection_files = json.loads((SELECTION_ADDITIONS / "freeze.json").read_text())[
        "files"
    ]
    if {p.name for p in SELECTION_ADDITIONS.iterdir()} != set(selection_files) | {
        "freeze.json"
    } or any(
        sha(SELECTION_ADDITIONS / n) != digest for n, digest in selection_files.items()
    ):
        raise ValueError("Frozen selection-evidence migration inventory changed")
    selection = json.loads((SELECTION_ADDITIONS / "protocol.json").read_text())
    from scripts.audit_liuren_selection_integrity import resolved_reference

    resolved_reference()
    if (
        sha(ROOT / "tests/fixtures/liuren_selection_integrity_v1/freeze.json")
        != selection["source_reference_sha256"]
        or sha(ROOT / "tests/fixtures/liuren_selection_erratum_v1/freeze.json")
        != selection["source_erratum_sha256"]
    ):
        raise ValueError("Selection migration source or erratum changed")
    ref["selection_additions"] = selection["allowed_values"]
    for name, digest in ref["sources"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Reused independent source changed")
    # Iteration46 adds a named, independently frozen year-fate layer. The
    # original iteration45 fixtures and their failed first annotation remain.
    from scripts.audit_jinkou_year_fate import PINS as YEAR_FATE_PINS
    from scripts.audit_jinkou_year_fate import references as year_fate_references

    year_fate_references()
    ref["additive_protocols"] = YEAR_FATE_PINS
    # The new chapter evidence does not rewrite the iteration45 sources,
    # annotations, time labels or failures. Pin its three added fields apart.
    if sha(CHAPTER_ADDITIONS / "freeze.json") != CHAPTER_PIN:
        raise ValueError("Frozen chapter golden-additions protocol changed")
    chapter_files = json.loads((CHAPTER_ADDITIONS / "freeze.json").read_text())["files"]
    if {p.name for p in CHAPTER_ADDITIONS.iterdir()} != set(chapter_files) | {
        "freeze.json"
    } or any(sha(CHAPTER_ADDITIONS / n) != d for n, d in chapter_files.items()):
        raise ValueError("Frozen chapter golden additions changed")
    chapter = json.loads((CHAPTER_ADDITIONS / "additions.json").read_text())
    from scripts.audit_jinkou_waseda_chapter import reference as chapter_reference

    chapter_reference()
    if (
        sha(ROOT / "tests/fixtures/jinkou_waseda_chapter_v1/freeze.json")
        != chapter["new_source_reference_sha256"]
        or sha(ROOT / "src/fatebridge/data/jinkou_waseda_chapter.json")
        != chapter["source_asset_sha256"]
        or set(chapter["allowed_paths"]) != CHAPTER_PATHS
    ):
        raise ValueError("Chapter golden additions differ from frozen source")
    ref["chapter_source_additions"] = chapter["allowed_paths"]
    # The new lookup layer has its own frozen source examples; it does not
    # relabel any earlier golden calculation or classical disagreement.
    from scripts.audit_liuren_god_yin import reference as god_yin_reference

    god_yin_reference()
    if sha(STRENGTH_ADDITIONS / "freeze.json") != STRENGTH_PIN:
        raise ValueError("Frozen strength-source migration protocol changed")
    strength_files = json.loads((STRENGTH_ADDITIONS / "freeze.json").read_text())[
        "files"
    ]
    if {p.name for p in STRENGTH_ADDITIONS.iterdir()} != set(strength_files) | {
        "freeze.json"
    } or any(sha(STRENGTH_ADDITIONS / n) != d for n, d in strength_files.items()):
        raise ValueError("Frozen strength-source migration values changed")
    strength = json.loads((STRENGTH_ADDITIONS / "protocol.json").read_text())
    from scripts.audit_jinkou_waseda_strength import reference as strength_reference

    strength_reference()
    if (
        sha(ROOT / "tests/fixtures/jinkou_waseda_strength_v1/freeze.json")
        != strength["new_source_reference_sha256"]
        or sha(ROOT / "src/fatebridge/data/jinkou_waseda_strength.json")
        != strength["runtime_asset_sha256"]
        or set(strength["allowed_source_paths"]) != STRENGTH_SOURCE_PATHS
    ):
        raise ValueError("Strength-source migration differs from frozen source")
    ref["strength_source_additions"] = strength
    from scripts.audit_jinkou_month_building import reference as month_reference

    month_reference()
    if sha(MONTH_ADDITIONS / "freeze.json") != MONTH_PIN:
        raise ValueError("Frozen month-building golden protocol changed")
    month_files = json.loads((MONTH_ADDITIONS / "freeze.json").read_text())["files"]
    if {p.name for p in MONTH_ADDITIONS.iterdir()} != set(month_files) | {
        "freeze.json"
    } or any(sha(MONTH_ADDITIONS / n) != digest for n, digest in month_files.items()):
        raise ValueError("Frozen month-building golden values changed")
    month = json.loads((MONTH_ADDITIONS / "protocol.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_month_building_v1/freeze.json")
        != month["source_reference_sha256"]
        or set(month["allowed_values"]) != MONTH_PATHS
        or set(month["added_qi_keys"]) != set(MONTH_KEYS)
        or month["trace_rule_id"] != "jinkou.month_day_qi"
        or month["trace_index"] != 9
    ):
        raise ValueError("Month-building migration differs from frozen scope")
    ref["month_building_additions"] = month
    return ref


def differences(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(old.keys() | new.keys()):
            p = path + "." + key if path else key
            if key not in old:
                out.append(dict(path=p, kind="added", new=new[key]))
            elif key not in new:
                out.append(dict(path=p, kind="removed", old=old[key]))
            else:
                out.extend(differences(old[key], new[key], p))
        return out
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [
            c
            for i, (a, b) in enumerate(zip(old, new))
            for c in differences(a, b, path + "." + str(i))
        ]
    return (
        []
        if type(old) is type(new) and old == new
        else [dict(path=path, kind="changed", old=old, new=new)]
    )


def at(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def replace_at(value: Any, path: str, new: Any) -> None:
    parts = path.split(".")
    parent = value
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
    parent[key] = copy.deepcopy(new)


def semantic_check(slug: str, value: dict[str, Any], ref: dict[str, Any]) -> None:
    e = ref["fixtures"][ref["context_by_slug"][slug]]
    obj = value["subresults"]["liureng_gods"] if slug == SLUGS[-1] else value
    pillars = obj["four_pillars"]
    board = obj["liureng"]
    for role in ("year", "month", "day", "hour"):
        assert (
            pillars[role]["stem"] + pillars[role]["branch"]
            == e["hour_pillar" if role == "hour" else role]
        ), (slug, role)
    assert board["month_general"]["branch"] == e["month_general"]
    assert board["four_lessons"][0]["upper_branch"] == e["gan_upper"]
    transmissions = [
        board["three_transmissions"][k] for k in ("initial", "middle", "final")
    ]
    assert [r["branch"] for r in transmissions] == e["transmissions"]
    assert [r["dun_stem"] for r in transmissions] == e["dun_stems"]
    assert (
        board["xun_head"] == e["xun_head"]
        and list(board["kongwang"][:2]) == e["empty_branches"]
    )
    lunar = obj["calendar_context"]["lunar_calendar"]
    assert (lunar["month"], lunar["day"]) == (e["lunar_month"], e["lunar_day"])
    if slug == "api_cn_jinkou":
        j = value["jinkou"]
        expected = ref["jinkou_april8"]
        assert [r["content"] for r in j["rows"]] == expected["positions"]
        assert j["overview"]["guishen"]["name"] == expected["god"]
        assert (
            j["overview"]["guishen"]["intrinsic_ganzhi"] == expected["intrinsic_ganzhi"]
        )
        assert j["overview"]["use_position"] == expected["polarity_use"]
    if slug == "api_cn_liureng_runyear":
        assert all(value["runyear"][k] == v for k, v in ref["runyear"].items())


def allowed(path: str, kind: str, slug: str) -> bool:
    # Shared non-Ren calendar, Qimen and Taiyi changes remain outside this plan.
    if slug == "api_cn_jinkou" and path in NATAL_COURSE_PATHS:
        return True
    if slug == "api_cn_jinkou" and path in MONTH_PATHS:
        return True
    if slug == "api_cn_jinkou" and kind == "added" and path in CHAPTER_PATHS:
        return True
    if slug == "api_cn_jinkou" and path in STRENGTH_SOURCE_PATHS:
        return True
    if slug == "api_cn_jinkou" and (
        path == "jinkou.year_fate"
        and kind == "added"
        or path
        in {"jinkou.ruleset.unresolved", "jinkou.ruleset.conventions.natal_absolute"}
    ):
        return True
    for prefix in ("liureng", "jinkou", "subresults.liureng_gods.liureng"):
        if path.startswith(prefix + "."):
            tail = path[len(prefix) + 1 :]
            if tail.split(".")[0] in NEW_LAYERS and kind == "added":
                return True
            if tail == "rule_trace":
                return True
            if tail in {"ruleset.version", "ruleset.source_title"}:
                return True
            if tail.startswith("ruleset.conventions.") and kind == "added":
                return True
            if tail.endswith("style_basis") and tail.startswith("four_lessons."):
                return True
            if tail == "calendar_policy.scope" or tail.endswith(
                ".published_date_reference"
            ):
                return True
    if "calendar_context.ren_calendar_policy." in path:
        return path.endswith(".scope") or path.endswith(".published_date_reference")
    if (
        path == "synthesis.source_profiles.liureng.0.source_title"
        or path == "synthesis.source_profiles.liureng.0.version"
    ):
        return True
    if path == "run_metadata.engine_is_approximate":
        return True
    if slug != SLUGS[-1] and (
        path == "snapshot_text" or path.startswith("snapshot_export.")
    ):
        return True
    return False


def verify_change(change: dict[str, Any], ref: dict[str, Any]) -> None:
    path = change["path"]
    if path in NATAL_COURSE_PATHS and path.startswith("jinkou."):
        assert change["new"] == ref["natal_course_additions"][path]
        if path != "jinkou.rule_trace":
            return
    if path in MONTH_PATHS and not path.startswith("snapshot"):
        assert change["new"] == ref["month_building_additions"]["allowed_values"][path]
        if any(path.endswith("." + key) for key in MONTH_KEYS) or path.endswith(
            "conventions.month_building"
        ):
            assert change["kind"] == "added"
    elif path in STRENGTH_SOURCE_PATHS:
        protocol = ref["strength_source_additions"]
        assert change["new"] == protocol["allowed_source_paths"][path]
        if path.endswith(".note"):
            assert change["kind"] == "changed"
            assert change["old"] == protocol["old_note"]
        else:
            assert change["kind"] == "added"
    elif path in CHAPTER_PATHS:
        assert change["kind"] == "added"
        assert change["new"] == ref["chapter_source_additions"][path]
    elif path == "jinkou.ruleset.unresolved":
        assert change["new"] == change["old"] + [
            "京本行年换岁边界及己亥行年见甲人元所指课干未裁定，未认证综合喜用"
        ]
    elif path == "jinkou.ruleset.conventions.natal_absolute":
        assert (
            change["new"]
            == "将命大绝取显式本命支，或明确birth_year_ganzhi的年支，与本次将神支核对京本四组配对；两者均缺仍未知，不以分析年日时、地分或行年替代本命"
        )
    elif path.endswith("style_basis"):
        assert (change["old"], change["new"]) == (
            ref["text_erratum"]["old"],
            ref["text_erratum"]["new"],
        )
    elif path == "run_metadata.engine_is_approximate":
        assert change["old"] is False and change["new"] is True
    elif path.endswith("rule_trace"):
        prior = {r["rule_id"]: r for r in change["old"]}
        current = {r["rule_id"]: r for r in change["new"]}
        assert len(current) == len(change["new"])
        for key, value in prior.items():
            actual = current[key]
            if actual == value:
                continue
            if path == "jinkou.rule_trace" and key == "jinkou.internal_strength":
                restored = copy.deepcopy(actual)
                for source_key in STRENGTH_SOURCE_KEYS:
                    source_path = (
                        "jinkou.internal_strength.source_evidence." + source_key
                    )
                    assert (
                        actual["result"]["source_evidence"][source_key]
                        == ref["strength_source_additions"]["allowed_source_paths"][
                            source_path
                        ]
                    )
                    if source_key == "note":
                        restored["result"]["source_evidence"][source_key] = ref[
                            "strength_source_additions"
                        ]["old_note"]
                    else:
                        del restored["result"]["source_evidence"][source_key]
                assert restored == value, "Old strength calculation or source changed"
            elif path == "jinkou.rule_trace" and key == "jinkou.month_day_qi":
                restored = copy.deepcopy(actual)
                for field in MONTH_KEYS:
                    assert (
                        actual["result"][field]
                        == ref["month_building_additions"]["allowed_values"][
                            "jinkou.qi_evidence." + field
                        ]
                    )
                    del restored["result"][field]
                assert restored == value, "Old month/day calculation changed"
            else:
                assert actual == value, "Old trace changed"
    elif change["kind"] == "removed":
        raise ValueError("Evidence migration cannot remove old facts")


def plan(
    slug: str, candidate: dict[str, Any], ref: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    from scripts.jinkou_archive_proofs import historical_pattern_proofs
    from scripts.liuren_course_archive import historical_course_conditions
    from scripts.liuren_cross_harmony_archive import historical_cross_harmony
    from scripts.liuren_day_placement_archive import (
        historical_day_placements,
        legacy_candidate_day_placements,
    )
    from scripts.liuren_ordered_archive import historical_ordered_patterns

    # Validate supplied proofs before removing only their *new* annotations
    # for the unchanged historical migration gates. Wrong proofs never vanish.
    candidate, candidate_cross_harmony = historical_cross_harmony(
        candidate, mode="strip"
    )
    candidate, candidate_day_placements = legacy_candidate_day_placements(candidate)
    candidate, candidate_course = historical_course_conditions(candidate, mode="strip")
    candidate, candidate_ordered = historical_ordered_patterns(candidate, mode="strip")
    candidate, candidate_proofs = historical_pattern_proofs(candidate, mode="strip")
    original = json.loads((ORIGINALS / (slug + ".json")).read_text())
    semantic_check(slug, original, ref)
    semantic_check(slug, candidate, ref)
    migrated = copy.deepcopy(original)
    changes = differences(original, candidate)
    applied = []
    retained = []
    for change in changes:
        if not allowed(change["path"], change["kind"], slug):
            if change["path"].startswith(
                (
                    "liureng.",
                    "jinkou.",
                    "subresults.liureng_gods.liureng.",
                    "four_pillars.",
                    "subresults.liureng_gods.four_pillars.",
                    "runyear.",
                )
            ):
                raise ValueError("Undeclared Ren calculation change: " + change["path"])
            retained.append(change)
            continue
        declared = ref["selection_additions"][slug]
        if change["path"] in declared:
            assert change["new"] == declared[change["path"]]
        if slug == "api_cn_jinkou" and change["path"] in NATAL_COURSE_PATHS:
            assert change["new"] == ref["natal_course_additions"][change["path"]]
        elif slug == "api_cn_jinkou" and change["path"] in MONTH_PATHS:
            assert (
                change["new"]
                == ref["month_building_additions"]["allowed_values"][change["path"]]
            )
        verify_change(change, ref)
        replace_at(migrated, change["path"], change["new"])
        applied.append(change)
    migrated, proof_supplement = historical_pattern_proofs(migrated)
    migrated, ordered_supplement = historical_ordered_patterns(migrated)
    migrated, course_supplement = historical_course_conditions(migrated)
    migrated, placement_supplement = historical_day_placements(migrated)
    migrated, cross_supplement = historical_cross_harmony(migrated)
    for addition in (
        proof_supplement["changes"]
        + ordered_supplement["changes"]
        + course_supplement["changes"]
        + placement_supplement["changes"]
        + cross_supplement["changes"]
    ):
        parents = [
            c
            for c in applied
            if addition["path"] == c["path"]
            or addition["path"].startswith(c["path"] + ".")
        ]
        if parents:
            # A previous migration can replace the whole trace list. Its old
            # value was checked above; retain that gate and separately record
            # the exact reversible new leaves in proof_supplement.
            for parent in parents:
                parent["new"] = copy.deepcopy(at(migrated, parent["path"]))
        else:
            applied.append(addition)
    # All changes outside this explicit ledger are still exactly the original.
    assert {c["path"] for c in differences(original, migrated)} == {
        c["path"] for c in applied
    }
    reverse = copy.deepcopy(migrated)
    for change in reversed(applied):
        if change["kind"] == "added":
            p, _, key = change["path"].rpartition(".")
            parent = at(reverse, p) if p else reverse
            del parent[key]
        else:
            replace_at(reverse, change["path"], change["old"])
    assert reverse == original
    from fatebridge.application.execution import OutputContractError, validate_output
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == KEYS[slug])
    # Canonical golden receipts intentionally omit UUIDs and generated_at.
    # Validate the complete business envelope, never invent those live fields.
    business = {k: v for k, v in migrated.items() if k != "run_metadata"}
    current_contract_error = None
    try:
        validate_output(spec, business)
    except OutputContractError as error:
        # These frozen envelopes predate nominal seasonal facts. Preserve that
        # exact current-contract failure; every other failure still propagates.
        if (
            str(error.__cause__)
            != "完整三合局体须保留同次月建及三传的名义季态与可空事实"
        ):
            raise
        current_contract_error = str(error.__cause__)
    semantic_check(slug, migrated, ref)
    return migrated, dict(
        slug=slug,
        derived_archive_pattern_proofs=proof_supplement,
        candidate_new_proofs_checked_before_legacy_comparison=candidate_proofs,
        derived_archive_ordered_patterns=ordered_supplement,
        candidate_ordered_patterns_checked_before_legacy_comparison=candidate_ordered,
        derived_archive_course_conditions=course_supplement,
        candidate_course_conditions_checked_before_legacy_comparison=candidate_course,
        derived_archive_day_placements=placement_supplement,
        candidate_day_placements_checked_before_legacy_comparison=candidate_day_placements,
        derived_archive_cross_harmony=cross_supplement,
        candidate_cross_harmony_checked_before_legacy_comparison=candidate_cross_harmony,
        applied=applied,
        retained_differences=retained,
        original_object_restored_exactly=True,
        complete_business_output_contract_passed=current_contract_error is None,
        current_contract_error=current_contract_error,
        canonical_receipt_scope="run_metadata omitted for business validation; live receipts have separate tests",
        hand_annotated_semantics_passed=True,
        original_sha256=sha(ORIGINALS / (slug + ".json")),
    )


def capture_candidates(folder: Path) -> None:
    """Real REST capture on the declared historical native/Moshier fixture."""
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from fatebridge.services.tool_catalog import CATALOG
    from tests.fixtures.surface_payloads import REST_POST_CASES
    from tests.golden.canonical import canonical_json
    from tests.golden.runner import freeze_clock, golden_ephemeris

    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / ("candidate-" + slug + ".json")).exists() for slug in SLUGS):
        raise FileExistsError("Capture refuses to replace existing candidate evidence")
    auth = api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={})
    with (
        patch.object(api, "API_KEY_AUTHENTICATOR", auth),
        golden_ephemeris(),
        freeze_clock(),
    ):
        client = TestClient(api.app)
        for slug in SLUGS:
            spec = next(s for s in CATALOG if s.key == KEYS[slug])
            path = spec.rest_path
            if path is None:
                raise ValueError("Declared golden tool has no REST endpoint")
            response = client.post(
                path, json=REST_POST_CASES[path](), params={"response_char_limit": 0}
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Golden capture {path} returned {response.status_code}: {response.text}"
                )
            (folder / ("candidate-" + slug + ".json")).write_text(
                canonical_json(response.json()) + "\n"
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--capture",
        action="store_true",
        help="Capture real four-tool REST results before auditing; refuses overwrite",
    )
    args = p.parse_args()
    watched = [
        q
        for q in (ROOT / "src/fatebridge").rglob("*")
        if q.is_file() and "__pycache__" not in q.parts and q.suffix != ".pyc"
    ] + [
        Path(__file__).resolve(),
        ROOT / "tests/golden/runner.py",
        ROOT / "tests/golden/canonical.py",
        ROOT / "tests/fixtures/surface_payloads.py",
    ]
    fingerprints = {str(q.relative_to(ROOT)): sha(q) for q in watched}
    ref = reference()
    if args.capture:
        capture_candidates(args.candidate_dir)
    reports = []
    ready = []
    for slug in SLUGS:
        candidate = json.loads(
            (args.candidate_dir / ("candidate-" + slug + ".json")).read_text()
        )
        value, record = plan(slug, candidate, ref)
        record["candidate_sha256"] = sha(
            args.candidate_dir / ("candidate-" + slug + ".json")
        )
        reports.append(record)
        ready.append((slug, value))
    if args.apply:
        if any(
            not record["complete_business_output_contract_passed"] for record in reports
        ):
            raise ValueError(
                "Historical envelopes do not satisfy the current complete contract; golden writes refused"
            )
        for slug, value in ready:
            target = ROOT / "tests/golden/snapshots" / (slug + ".json")
            assert (
                target.read_bytes() == (ORIGINALS / (slug + ".json")).read_bytes()
            ), "Concurrent golden change"
        for slug, value in ready:
            (ROOT / "tests/golden/snapshots" / (slug + ".json")).write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            )
    report = dict(
        records=reports,
        applied=args.apply,
        additive_protocols=ref["additive_protocols"],
        initial_annotation_input_checks=initial_annotation_checks(),
        initial_annotation_input_mismatches=sum(
            not r["matched"] for r in initial_annotation_checks()
        ),
        initial_annotation_replaced_by_explicit_input_correction=True,
        implementation_sha256=fingerprints,
        implementation_unchanged=fingerprints
        == {str(q.relative_to(ROOT)): sha(q) for q in watched},
        initial_protocol_old_lesson_text_preservation_passed=not any(
            c["path"].endswith("style_basis") for r in reports for c in r["applied"]
        ),
        corrected_protocol_lesson_text_changes=[
            dict(slug=r["slug"], path=c["path"], old=c["old"], new=c["new"])
            for r in reports
            for c in r["applied"]
            if c["path"].endswith("style_basis")
        ],
        full_linux_byte_acceptance=False,
        new_independent_physical_events=0,
        new_classical_cases=0,
        new_empirical_events=0,
        full_classical_conformance=False,
        goal_complete=False,
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "records"}, ensure_ascii=False
        )
    )
    return (
        0
        if all(
            record["complete_business_output_contract_passed"]
            for record in report["records"]
        )
        else 1
    )


def initial_annotation_checks() -> list[dict[str, Any]]:
    """Keep the initial annotation's actual mismatch, even after correction."""
    ref = json.loads((ORIGINALS / "reference.json").read_text())
    rows = []
    for slug in SLUGS:
        original = json.loads((ORIGINALS / (slug + ".json")).read_text())
        try:
            semantic_check(slug, original, ref)
        except AssertionError as exc:
            rows.append(dict(slug=slug, matched=False, error=str(exc)))
        else:
            rows.append(dict(slug=slug, matched=True))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
