"""A reference supplement cannot rewrite the parent study or its source window."""

import asyncio
import hashlib
import json
from calendar import month_name
from datetime import date, timedelta
from pathlib import Path

import pytest

import fatebridge.validation.meihua_weather_reference_study as module
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def shell(tmp_path, change=None):
    base = tmp_path / "study"
    plan = {
        "id": "meihua_weather_reference_baseline_supplement_v1",
        "study_kind": "posthoc_reference_baseline_supplement_not_preregistered_not_new_prediction_test",
        "climatology_training": ["1991-01-01", "2021-01-01"],
        "threshold_mm": "0.1",
        "parent_files_sha256": {},
    }
    parent = {
        "scenario_order": ["calendar_season_supplied", "season_not_supplied"],
        "cohorts": {
            name: [(start + timedelta(days=i)).isoformat() for i in range(n)]
            for name, start, n in [
                ("primary_2026_ytd_through_last_complete_month", date(2026, 1, 1), 273),
                ("retrospective_2024", date(2024, 1, 1), 366),
                ("retrospective_2025", date(2025, 1, 1), 365),
            ]
        },
    }
    if change:
        change(plan, parent)
    put(base / "plan.json", plan)
    put(base / "parent/plan.json", parent)
    implementation = Path(module.__file__).parent
    put(
        base / "reference-lock.json",
        {
            "study_files": {
                "plan.json": hashlib.sha256(
                    (base / "plan.json").read_bytes()
                ).hexdigest()
            },
            "implementation_files": {
                "meihua_weather_reference_study.py": hashlib.sha256(
                    (implementation / "meihua_weather_reference_study.py").read_bytes()
                ).hexdigest()
            },
        },
    )
    return base


@pytest.mark.parametrize(
    "field", ["threshold_mm", "climatology_training", "study_kind"]
)
def test_protocol_cannot_choose_new_threshold_training_years_or_preregistration(
    tmp_path, field
):
    base = shell(tmp_path, lambda p, _: p.update({field: "changed"}))
    with pytest.raises(ValueError, match="fixed scope"):
        module.audit_weather_reference_study(base)


def test_changed_source_stops_before_any_observation_scoring(tmp_path):
    base = shell(tmp_path)
    put(base / "plan.json", {})
    with pytest.raises(ValueError, match="Locked reference"):
        module.audit_weather_reference_study(base)


def test_lock_path_escape_is_not_a_replacement_source(tmp_path):
    base = shell(tmp_path)
    put(
        base / "reference-lock.json",
        {"study_files": {"../outside": "x"}, "implementation_files": {}},
    )
    with pytest.raises(ValueError, match="Locked reference"):
        module.audit_weather_reference_study(base)


def test_all_old_cohort_dates_still_required_even_for_a_posthoc_reference(tmp_path):
    base = shell(tmp_path, lambda _, p: p["cohorts"]["retrospective_2024"].pop())
    with pytest.raises(ValueError, match="Every original locked date"):
        module.audit_weather_reference_study(base)


def test_unknown_or_reordered_scenario_cannot_replace_the_old_primary(tmp_path):
    base = shell(tmp_path, lambda _, p: p["scenario_order"].reverse())
    with pytest.raises(ValueError, match="cohorts and scenarios"):
        module.audit_weather_reference_study(base)


def test_normals_parser_selects0_1mm_column_and_all_twelve_months():
    rows = [
        f"<tr><td>{month_name[m]}</td><td>999</td><td>80</td><td>{m}.00</td><td>25</td><td>50</td></tr>"
        for m in range(1, 13)
    ]
    table = "<table><th>0.1 mm /25 mm /50 mm</th>" + "".join(rows) + "</table>"
    assert module.official_normal_rain_days(table) == [f"{m}.00" for m in range(1, 13)]
    with pytest.raises(ValueError, match="ambiguous"):
        module.official_normal_rain_days(table + table)
    with pytest.raises(ValueError, match="twelve"):
        module.official_normal_rain_days(table.replace(rows[0], ""))


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_conditional_reference_counts_and_unknown_vintages_survive_all_surfaces(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = {"interpretation_topic": "weather"}
    if tool == "meihua_cast":
        payload["casting"] = {
            "method": "existing",
            "hexagram_code": "001010",
            "moving_line": 4,
        }
    else:
        payload.update(
            analysis_year=2026,
            analysis_month=2,
            analysis_day=19,
            analysis_hour=6,
            analysis_timezone="Asia/Hong_Kong",
        )
    fields = [
        "interpretation.weather.research_validation",
        "interpretation.weather.single_forecast",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        metadata = weather["research_validation"]
        assert metadata["version"] == "1.6.0"
        assert metadata["correct"] == 128
        assert metadata["additional_profile_audits"][0]["correct"] == 16
        assert metadata["current_profile_study"]["primary"]["correct"] == 29
        reference = metadata["reference_baseline_supplement"]
        assert reference["training_days"] == 10958
        assert reference["all12_official_normals_match_published_precision"]
        cohort = reference["by_cohort"]["primary_2026_ytd_through_last_complete_month"]
        assert cohort["conditional_full_cohort_reference_correct"] == {
            "persistence": 183,
            "monthly_climatology": 190,
        }
        assert cohort["usable_reference_days_at_historic_issue"] == {
            "persistence": 0,
            "monthly_climatology": 0,
        }
        assert (
            cohort["scenarios"]["calendar_season_supplied"][
                "operational_superiority_gate"
            ]
            is None
        )
        assert reference["real_world_predictive_efficacy_established"] is False
        assert weather["single_forecast"] is None
