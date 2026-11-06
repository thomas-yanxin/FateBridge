"""Revised quotations and calculation receipts survive projection and delivery."""

import json
from pathlib import Path

import pytest

from tests.evaluation import test_agentic_nested_outputs as adapters
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.support.result_delivery import assert_same_run_receipt, reconstruct

rest = adapters.rest
BASE = Path(__file__).parents[1] / "fixtures/liuyao_quote_collation_v43"
ERRATA = json.loads((BASE / "errata.json").read_text())["corrections"]
ROOT = "liuyao_evidence.conditional_analysis"
FIELDS = [ROOT + ".stage_knowledge", ROOT + ".cessation_conditions"]
PAYLOAD = dict(
    date="2004-06-02",
    time="12:00:00",
    zone="Asia/Shanghai",
    gua_code="100100",
    changed_code="100101",
    focus_line=6,
    timing_days=0,
)


@pytest.fixture(autouse=True)
def auto_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)


def assert_quotes(body):
    conditional = body["liuyao_evidence"]["conditional_analysis"]
    for key, artifact in [
        ("stage_knowledge", "liuyao-stages-v15.json"),
        ("cessation_conditions", "liuyao-cessation-v17.json"),
    ]:
        expected = next(e for e in ERRATA if e["artifact"] == artifact)
        detail = conditional[key]
        assert detail["ruleset_version"] == expected["new_ruleset_version"]
        clause = next(c for c in detail["clauses"] if c["id"] == expected["clause_id"])
        assert clause["quote"] == expected["new_quote"]
        assert clause["quotation_revision"] == expected["revision"]
    assert conditional["stage_knowledge"]["missing_stages"]["火"] == ["帝旺", "绝"]


def test_revised_quotes_survive_strict_projection_on_three_local_adapters(
    rest, tmp_path, capsys
):
    for body in all_surfaces(PAYLOAD, FIELDS, rest, tmp_path, capsys):
        assert_quotes(body)
        assert not body.get("projection_warnings")


def test_same_run_reconstruction_keeps_corrected_quotes_and_calculated_facts(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery

    store = delivery.ResultStore(tmp_path / "quote-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(PAYLOAD, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert_quotes(original)
        assert (
            original["liuyao_evidence"]["conditional_analysis"]["cessation_conditions"][
                "focus"
            ]["changed"]["condition_match"]
            is False
        )
