"""Strict readout-only comparison for five unaffected frozen legacy charts."""

import json
from copy import deepcopy
from pathlib import Path


def without_v31_readout(value):
    result = deepcopy(value)
    evidence = result["liuyao_evidence"]
    control = evidence["conditional_analysis"]["control_conditions"]
    profile = json.loads(
        (Path(__file__).parent / "liuyao_void_control_v31/profile.json").read_text(
            encoding="utf-8"
        )
    )
    published = control.pop("void_fill_qualification")
    assert published == dict(
        ruleset_id=profile["ruleset_id"],
        ruleset_version=profile["ruleset_version"],
        source_sha256=profile["source"]["sha256"],
        source_urls=[
            profile["source"]["url"] + "#page=" + str(c["pdf_page"])
            for c in profile["clauses"]
        ],
        clauses=profile["clauses"],
        precedence=profile["precedence"],
        scope=profile["scope"],
    )
    for p in control["controls"]:
        # No new numeric effect is permitted in these five particular charts.
        assert p.pop("source_void_fill_control_condition") is False
        assert p.pop("source_void_fill_used") is False
        assert (
            p.pop("void_fill_qualification_path")
            == "liuyao_evidence.conditional_analysis.control_conditions.void_fill_qualification"
        )
    added = [
        t
        for t in evidence["rule_trace"]
        if t["rule_id"] == "current_void_fill_directed_control"
    ]
    assert len(added) == 1 and added[0]["sources"] == published["source_urls"]
    evidence["rule_trace"] = [t for t in evidence["rule_trace"] if t not in added]
    lines = result["snapshot_text"].splitlines()
    assert lines.count(profile["scope"]) == 1
    result["snapshot_text"] = "\n".join(t for t in lines if t != profile["scope"])
    return result
