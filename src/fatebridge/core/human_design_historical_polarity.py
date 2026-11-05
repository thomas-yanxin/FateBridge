"""An unresolved historical58.5 correction, separate from selected fixings.

The notice reports a teaching correction; it is not an authenticated publisher
master. Existing official chart markers disagree with applying that amendment.
Only the nominal chart is compared, using its actual natal donor paths.
"""

from typing import Any

from fatebridge.core.human_design_depth import line_fixings

METHOD = "human_design_historical_polarity_v1"
NOTICE = "https://www.humandesignsystem.com/archive/newsletters/0904.pdf"
SCOPE = "仅对名义盘58.5比较2001字面星体表与2002通知的条件假设，沿用本盘双侧同门／谐振门固定机制。通知适用版次未定，现有两张官方盘标记与其冲突；不改默认、不改完整线义，也不外推其他联合见证或现实事件。"


def source_records() -> list[dict[str, Any]]:
    return [
        {
            "id": "zc_design_2002_notice",
            "url": NOTICE,
            "pdf_sha256": "50997eddd5ddfea0b413f3a2a885baa1e0e538c1d0adca726319b2ed4c6f9c9f",
            "page_one_based": 1,
            "printed_date": "2002-03-17",
            "heading": "Rave I'Ching Error Alert",
            "attribution": "zc design newsletter reports Ra's teaching correction; not an authenticated Jovian publisher erratum or direct class transcript",
            "reported_fact": "58.5 Moon and Sun both exalted; reports corrected colour and black-and-white printings without identifying the captured2001PDF",
            "applicability_to_selected_2001_edition": "unresolved",
        },
        *[
            {
                "id": ident,
                "url": "https://jovianarchive.com/pages/get-your-human-design-chart",
                "archive_path": "tests/data/human_design/source-charts/"
                + ident
                + ".pdf",
                "pdf_sha256": sha,
                "page_one_based": 1,
                "observed_target": "personality.Sun58.5",
                "observed_marker": "downward_triangle",
                "marker_meaning": "detriment",
                "method": "visual review of both preselected existing original768cohort cases; no new chart sample",
            }
            for ident, sha in (
                (
                    "profile-58-5-1",
                    "cd4ddc0a77b9141cdebb32243d703eaab9f7df929401ea644b6a14bd4c46e22c",
                ),
                (
                    "profile-58-5-2",
                    "c288a8db57b4f9afe896d90a35ccba8c8aee59a0607d4c0b250a6b51d00bee77",
                ),
            )
        ],
    ]


def ruleset() -> dict[str, Any]:
    return {
        "id": METHOD,
        "version": "1.0.0",
        "author": "FateBridge conditional comparison of conflicting source observations",
        "source_kind": "historical_third_party_notice_and_existing_official_chart_markers",
        "sources": {s["id"]: s["url"] for s in source_records()},
        "source_records": source_records(),
        "scope": SCOPE,
    }


def comparison_report(chart: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for fix in line_fixings(chart["activations"]):
        if (fix["gate"], fix["line"]) != (58, 5):
            continue
        if (fix["exaltation_planet"], fix["detriment_planet"]) != ("Moon", "Sun"):
            raise ValueError(
                "Selected58.5 catalogue changed; review historical comparison"
            )
        original = fix["fixing_planets"]
        # Move only Sun donors. Keep each actual side/index/relation, including
        # harmonic and opposite-side donors, and never introduce node donors.
        moved = [d for d in original["detriment"] if d["body"] == "Sun"]
        exalted = sorted(
            [*original["exaltation"], *moved],
            key=lambda d: (
                0 if d["side"] == "personality" else 1,
                int(d["calculation_path"].rsplit(".", 1)[1]),
            ),
        )
        detriment = [d for d in original["detriment"] if d["body"] != "Sun"]
        state = (
            "juxtaposition"
            if exalted and detriment
            else "exaltation" if exalted else "detriment" if detriment else "unfixed"
        )
        rows.append(
            {
                "side": fix["side"],
                "body": fix["body"],
                "gate": 58,
                "line": 5,
                "calculation_path": fix["calculation_path"],
                "selected_2001_fixing_state": fix["fixing_state"],
                "selected_2001_fixing_planets": original,
                "conditional_2002_fixing_state": state,
                "conditional_2002_fixing_planets": {
                    "exaltation": exalted,
                    "detriment": detriment,
                },
                "fixing_state_changed": state != fix["fixing_state"],
                "conditional_model_selected": False,
            }
        )
    return {
        "ruleset_id": METHOD,
        "ruleset": ruleset(),
        "status": "unresolved_historical_source_conflict",
        "selected_polarity_table": "rave_2001_literal_moon_exaltation_sun_detriment",
        "conditional_hypothesis": "zc_design_2002_moon_and_sun_exaltation_no_sun_detriment",
        "conditional_hypothesis_is_complete_line_reading": False,
        "default_changed": False,
        "source_applicability_resolved": False,
        "source_conflict_resolved": False,
        "nominal_recipient_count": len(rows),
        "nominal_changed_state_count": sum(r["fixing_state_changed"] for r in rows),
        "nominal_recipients": rows,
        "scope": SCOPE,
    }


def context_reading(report: dict[str, Any]) -> dict[str, Any]:
    changes = [
        r["calculation_path"]
        for r in report["nominal_recipients"]
        if r["fixing_state_changed"]
    ]
    text = (
        "58.5存在未决来源分歧：2001字面表列月亮上升、太阳下降；2002年zc design通知转述两者均上升，"
        "但两张预选官方盘的人格太阳58.5均显示下降标记，通知适用版次尚未核定。"
        f"本名义盘有{report['nominal_recipient_count']}个58.5位置；按通知条件重分太阳触发极性，"
        f"固定状态将变{report['nominal_changed_state_count']}处。"
        + (
            "变化位置为"
            + "、".join(changes)
            + "；逐项前后极性及实际触发路径见nominal_recipients。"
            if changes
            else ""
        )
        + "当前逐项reading仍解释所选2001计算；此比较不提供完整58.5线义或现实预测，也未裁定来源冲突。"
    )
    return {
        "text": text,
        "basis": [
            {"path": "historical_polarity_context." + k, "value": report[k]}
            for k in (
                "nominal_recipient_count",
                "nominal_changed_state_count",
                "source_conflict_resolved",
            )
        ],
        "source_urls": [NOTICE, source_records()[1]["url"]],
    }


def add_historical_polarity_evidence(
    chart: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    report = comparison_report(chart)
    evidence["historical_polarity_context"] = report
    evidence["interpretation"]["historical_polarity_context"] = context_reading(report)
    evidence["interpretation"]["basis"].append("historical_polarity_context")
    evidence["rulesets"].append(ruleset())
    evidence["rule_trace"].append(
        {
            "rule_id": METHOD,
            "ruleset_id": METHOD,
            "inputs": {"activation_path": "activations"},
            "result": {
                "context_path": "historical_polarity_context",
                "default_changed": False,
            },
            "source_url": NOTICE,
        }
    )
    return evidence
