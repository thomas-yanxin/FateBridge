"""Qualify only the new source/clock presentation before old-fact comparison.

The expected join uses frozen literal references, never production join/render
functions. Original archived outputs and all non-presentation values are kept.
"""

import json
from copy import deepcopy
from pathlib import Path

from tests.canping_scope_fixture_compat import (
    rewind_scope_receipt_checked,
    upgrade_scope_receipt_checked,
)

ROOT = Path(__file__).parent / "fixtures/canping_reading_context_v1"
FACTS = json.loads((ROOT / "reference-v2.json").read_bytes())
TEXT = json.loads((ROOT / "presentation-migration-reference.json").read_bytes())
POLICY = "canping_schedule_source_mapping_v1"
MARKER = "[配运原典与日期映射]"
POLICIES = {
    "explicit_fixed_offset": "explicit_fixed_offset_assumption; no_regional_future_rules",
    "pytz": "pinned_regional_rules; subject_to_future_legislation",
}


def expected_context(value):
    profile = value["profile_id"]
    assert value["summary"] == TEXT["summary_by_profile"][profile]
    assert value["sources"] == FACTS["books"]
    assert value["future_clock_policy"] == POLICIES[value["timezone_rules"]["database"]]
    assert value["whole_book_alignment_established"] is False
    assert value["real_world_efficacy_validated"] is False
    if profile == "legacy_minggong_v1":
        kind = "legacy"
        assert value["has_actual_date_mapping"] is False
    else:
        kind = (
            "fixed"
            if value["timezone_rules"]["database"] == "explicit_fixed_offset"
            else "regional"
        )
        assert value["has_actual_date_mapping"] is True
    return {
        "profile_id": profile,
        "future_clock_policy": value["future_clock_policy"],
        "timezone_spec": value["timezone_spec"],
        "date_mapping_statement": TEXT["date_templates"][kind].format(
            zone=value["timezone_spec"]
        ),
        "source_citations": [
            {
                "source_id": source_id,
                **deepcopy(book),
                "pdf_pages": FACTS["pdf_pages"][source_id],
                "roles": FACTS["roles_by_profile"][profile][source_id],
            }
            for source_id, book in FACTS["books"].items()
        ],
    }


def _render(summary, scope, context=None):
    lines = [MARKER, summary]
    if context is not None:
        lines.append(context["date_mapping_statement"])
        for citation in context["source_citations"]:
            pages = "、".join(str(p) for p in citation["pdf_pages"])
            roles = "、".join(TEXT["role_labels"][r] for r in citation["roles"])
            lines.append(
                f"出处：《{citation['title']}》；{citation['edition']}；"
                f"PDF第{pages}页；本次角色：{roles}。书影：{citation['url']}"
            )
    lines.append(scope)
    return "\n".join(lines)


def _replace_exact_block(snapshot, expected, replacement):
    assert snapshot.count(MARKER) == 1
    start = snapshot.index(MARKER)
    following = snapshot.find("\n\n[", start)
    end = len(snapshot) if following < 0 else following
    assert snapshot[start:end].strip() == expected.strip()
    return snapshot[:start] + replacement + snapshot[end:]


def _source_trace(output):
    rows = [
        r for r in output["numerology_evidence"]["rule_trace"] if r["rule_id"] == POLICY
    ]
    assert len(rows) == 1
    return rows[0]


def rewind_reading_context_checked(current):
    result = rewind_scope_receipt_checked(current)
    value = result["canping_timing"]["schedule_basis"]
    expected = expected_context(value)
    assert value["reading_context"] == expected
    assert value["scope_statement"] == TEXT["scope_after"]
    trace = _source_trace(result)
    assert trace["facts"] == value
    before = _render(value["summary"], TEXT["scope_before"])
    after = _render(value["summary"], TEXT["scope_after"], expected)
    result["snapshot_text"] = _replace_exact_block(
        result["snapshot_text"], after, before
    )
    del value["reading_context"]
    value["scope_statement"] = TEXT["scope_before"]
    trace["facts"] = deepcopy(value)
    return result


def upgrade_prior_reading_presentation(output):
    result = deepcopy(output)
    value = result["canping_timing"]["schedule_basis"]
    assert "reading_context" not in value
    assert value["scope_statement"] == TEXT["scope_before"]
    trace = _source_trace(result)
    assert trace["facts"] == value
    expected = expected_context(value)
    before = _render(value["summary"], TEXT["scope_before"])
    after = _render(value["summary"], TEXT["scope_after"], expected)
    result["snapshot_text"] = _replace_exact_block(
        result["snapshot_text"], before, after
    )
    value["reading_context"] = expected
    value["scope_statement"] = TEXT["scope_after"]
    trace["facts"] = deepcopy(value)
    result = upgrade_scope_receipt_checked(result)
    # The inverse must recover every original field and string exactly.
    assert rewind_reading_context_checked(result) == output
    return result


def upgrade_prior_reading_fault(original, faulty):
    """Replay the exact original contradiction on a current presentation.

    Unlike accepting obsolete snapshots as invalid, this keeps each negative
    probe meaningful: stripping only the new presentation must recover the
    complete frozen faulty output, including every original wrong value.
    """
    result = upgrade_prior_reading_presentation(original)

    def patch(old, bad, new, path=()):
        if old == bad:
            return new
        if isinstance(old, dict) and isinstance(bad, dict):
            value = deepcopy(new)
            for key in old.keys() - bad.keys():
                value.pop(key, None)
            for key in bad:
                value[key] = (
                    patch(old[key], bad[key], value[key], path + (key,))
                    if key in old
                    else deepcopy(bad[key])
                )
            return value
        if isinstance(old, list) and isinstance(bad, list) and len(old) == len(bad):
            assert len(new) == len(old)
            return [
                patch(a, b, c, path + (i,))
                for i, (a, b, c) in enumerate(zip(old, bad, new))
            ]
        if path == ("snapshot_text",):
            summary = original["canping_timing"]["schedule_basis"]["summary"]
            replacement = bad[bad.index(MARKER) :].splitlines()[1]
            assert old.replace(summary, replacement) == bad
            assert new.count(summary) == old.count(summary)
            return new.replace(summary, replacement)
        return deepcopy(bad)

    result = patch(original, faulty, result)
    stripped = rewind_scope_receipt_checked(result)
    expected = expected_context(original["canping_timing"]["schedule_basis"])
    for value in (
        stripped["canping_timing"]["schedule_basis"],
        _source_trace(stripped)["facts"],
    ):
        assert value.pop("reading_context") == expected
        if value["scope_statement"] == TEXT["scope_after"]:
            value["scope_statement"] = TEXT["scope_before"]
    snapshot = stripped["snapshot_text"]
    shown_summary = snapshot[snapshot.index(MARKER) :].splitlines()[1]
    stripped["snapshot_text"] = _replace_exact_block(
        snapshot,
        _render(shown_summary, TEXT["scope_after"], expected),
        _render(shown_summary, TEXT["scope_before"]),
    )
    assert stripped == faulty
    return result
