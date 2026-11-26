"""Keep rejected strength witnesses, whole-source failures and old cards visible."""

import pytest

from tests.support.transports import SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

KEYS = ("暖局与用神", "日元强弱与性情措辞", "根位与有效接引")

rest = _shared_rest


@pytest.mark.parametrize("key", KEYS)
def test_new_source_conditions_survive_rest_native_mcp_and_cli(
    key, surface_calls
) -> None:
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": "classical_force_semantics", "key": key}
    options = {"detail": "audit"}
    http, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    value = http.json()
    curation = value["provenance"]["entry_curation"]
    assert (
        curation["source_refs"][0]["source_url"]
        == "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf"
    )
    assert (
        curation["review_status"]
        == "single_developer_source_reading_external_review_pending"
    )
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    assert curation["source_refs"][0]["edition"]
    if key == "日元强弱与性情措辞":
        assert len(value["tips"]) == 8
        assert curation["method_id"] == "dtcw1947_body_vocabulary_semantics_v3"
        assert curation["entry_revision"] == 3
        assert len(curation["source_relation_binding"]["rows"]) == 20
    else:
        assert len(value["tips"]) == 5
        assert curation["entry_revision"] == 1
    if key == "暖局与用神":
        assert "用神必在酉金" in value["rendered_text"]
        assert "用神不在丙火而在辰土" in value["rendered_text"]
    else:
        pass
