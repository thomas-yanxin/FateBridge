"""Source-rule geometry stays fixed while modern prose stops asserting facts."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

REFERENCE = Path(__file__).parent / "fixtures/meihua_closure_v1"
CASES = json.loads((REFERENCE / "oracle.json").read_text())["cases"]


def resolve(output, path):
    value = output
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def check_editorial(output):
    interpretation = output["interpretation"]
    phase = interpretation["moving_line_phase"]
    assert phase["source_kind"] == "modern_editorial_position_template"
    assert phase["real_stage_inferred"] is False
    for row in interpretation["line_oracles"]:
        assert row["timing_scope"] == "modern_action_order_hint_not_event_time"
        assert (
            row["transition_scope"]
            == "computed_hexagram_change_not_real_outcome_forecast"
        )
        assert "现代爻位联想" in row["position_hint"]
        assert "计算所得变卦" in row["transition"]
        assert "不证明现实走势" in row["transition"]
    modern = json.dumps(
        {
            "phase": phase,
            "lines": [
                {
                    k: row[k]
                    for k in ["position_hint", "transition", "body_use_adjustment"]
                }
                for row in interpretation["line_oracles"]
            ],
            "changed_reading": interpretation["changed_reading"],
            "body_use_reading": interpretation["body_use_reading"],
            "action_hint": interpretation["action_hint"],
        },
        ensure_ascii=False,
    )
    for unsupported in [
        "事情已到卡口",
        "事情已触及主轴",
        "事情来到尾段",
        "事在初起",
        "事情到了进退两难",
        "局面开始真正进入",
        "已到主轴结果位",
        "事已近尾",
        "局面多转向",
        "后续多转向",
        "外部资源会反过来扶助自身",
        "客观环境对主体形成压制",
    ]:
        assert unsupported not in modern


def test_reference_literals_and_source_images_are_unchanged():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert manifest["frozen_before_product_change"]
    assert not manifest["expected_values_generated_by_production"]
    assert manifest["cases"] == len(CASES) == 384
    assert manifest["new_real_observations"] == 0
    for name, expected in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("line", range(1, 7))
def test_every_actual_and_hypothetical_line_has_conditional_modern_hints(line):
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "011010", "moving_line": line}
    )
    check_editorial(out)
    assert out["interpretation"]["moving_line_oracle"]["line"] == line
    assert sum(row["is_active"] for row in out["interpretation"]["line_oracles"]) == 1


def test_all384_classical_geometries_relations_and_verses_remain_bound_to_their_cast():
    for expected in CASES:
        out = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": expected["code"],
                "moving_line": expected["line"],
            }
        )
        cast, reading = out["meihua"], out["interpretation"]
        assert [
            cast[name]["binary_code"]
            for name in ["base_hexagram", "changed_hexagram", "mutual_hexagram"]
        ] == [expected["code"], expected["changed"], expected["mutual"]]
        assert (cast["body_trigram"]["name"], cast["use_trigram"]["name"]) == (
            expected["body"],
            expected["use"],
        )
        for actual, reference in zip(
            cast["stage_relations"], expected["roles"], strict=True
        ):
            assert all(actual[k] == v for k, v in reference.items())
            assert actual["body"] == expected["body"]
            fact = resolve(out, actual["fact_path"])
            assert (fact["name"], fact["element"]) == (
                reference["trigram"],
                reference["element"],
            )
        assert {
            (e["controller_role"], e["target_role"])
            for e in reading["internal_countercontrol"]["control_edges"]
        } == {tuple(edge) for edge in expected["direct_control_edges"]}
        assert (
            reading["classical_text_reference"]["moving_yaoci"]
            == cast["base_hexagram"]["classical"]["yaoci"][expected["line"] - 1]
        )
        check_editorial(out)


@pytest.mark.parametrize("day", [3, 4])
def test_time_entry_uses_the_same_editorial_scope_without_changing_calendar(day):
    out = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
    )
    check_editorial(out)
    assert out["summary"] == out["interpretation"]["comprehensive_judgement"]
    assert out["meihua"]["calendar_policy"]["solar_term_date_reference"]
