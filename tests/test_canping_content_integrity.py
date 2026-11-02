"""An unreviewed literal edit cannot inherit a reviewed revision's status."""

import json
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.utils.errors import NumerologySourceError
from tests.test_agentic_nested_outputs import SPECS
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
REFERENCE = Path(__file__).parent / "fixtures/numerology_knowledge_v1"


@pytest.fixture(autouse=True)
def isolated_loaded_source(monkeypatch):
    loaded = texts._loaded
    loaded.cache_clear()
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    yield
    loaded.cache_clear()


def replace_source(monkeypatch, tmp_path, comparison, change):
    attribute = "WITNESSES_PATH" if comparison else "COLLATION_PATH"
    data = json.loads(getattr(texts, attribute).read_bytes())
    if change == "literal":
        if comparison:
            data["entries"][0]["text"] = "未经来源核准的替换原文。"
        else:
            data["entries"][0]["cells"]["male"] = "未经来源核准的替换原文。"
    elif change == "title":
        data["source_title"] = "另一部书"
    elif change == "pdf_identity":
        data["source_pdf_sha256"] = "0" * 64
    elif change == "review":
        data["review_status"] = "independently_verified_complete"
    elif change == "clear_uncertainty":
        if comparison:
            entry = next(e for e in data["entries"] if e.get("reading_uncertainties"))
            entry["text"] = entry["text"].replace("□", "字")
            del entry["reading_uncertainties"]
        else:
            entry = next(e for e in data["entries"] if e.get("reading_uncertainties"))
            for kind in entry["reading_uncertainties"]:
                entry["cells"][kind] = entry["cells"][kind].replace("□", "字")
            del entry["reading_uncertainties"]
    else:
        raise AssertionError(change)
    path = tmp_path / (attribute + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    monkeypatch.setattr(texts, attribute, path)
    return data


@pytest.mark.parametrize("comparison", [False, True])
@pytest.mark.parametrize(
    "change", ["literal", "title", "pdf_identity", "review", "clear_uncertainty"]
)
def test_structurally_valid_unreviewed_source_cannot_keep_original_review_status(
    comparison, change, monkeypatch, tmp_path
):
    replace_source(monkeypatch, tmp_path, comparison, change)
    expected = (
        "invalid_canping_witness_collation"
        if comparison
        else "invalid_canping_text_collation"
    )
    with pytest.raises(NumerologySourceError) as error:
        texts.source_readings(comparison=comparison)
    assert error.value.reason == expected
    assert error.value.as_result()["status_code"] == 503
    assert error.value.as_result()["retryable"] is False


@pytest.mark.parametrize("comparison", [False, True])
def test_formatting_is_independent_of_reviewed_text_but_loaded_byte_hash_is_actual(
    comparison, monkeypatch, tmp_path
):
    import hashlib

    original = texts.source_readings(comparison=comparison)
    attribute = "WITNESSES_PATH" if comparison else "COLLATION_PATH"
    path = tmp_path / "reformatted.json"
    path.write_text(json.dumps(original, ensure_ascii=True, sort_keys=True, indent=4))
    monkeypatch.setattr(texts, attribute, path)
    actual = texts.source_readings(comparison=comparison)
    assert actual == original
    summary = texts.witness_summary() if comparison else texts.collation_summary()
    assert summary["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    if not comparison:
        assert summary["collated_cells"] == 1123
        assert summary["pending_cells"] == 47


@pytest.mark.parametrize("comparison", [False, True])
def test_detached_reference_cannot_modify_cached_reviewed_content(comparison):
    original = texts.source_readings(comparison=comparison)
    returned = texts.source_readings(comparison=comparison)
    returned["entries"].clear()
    returned["review_status"] = "invented"
    assert texts.source_readings(comparison=comparison) == original


@pytest.mark.parametrize("comparison", [False, True])
@pytest.mark.parametrize("content", ["not json", "[]", None])
def test_missing_or_malformed_internal_source_is_a_source_error(
    comparison, content, monkeypatch, tmp_path
):
    attribute = "WITNESSES_PATH" if comparison else "COLLATION_PATH"
    path = tmp_path / "broken.json"
    if content is not None:
        path.write_text(content)
    monkeypatch.setattr(texts, attribute, path)
    with pytest.raises(NumerologySourceError) as error:
        texts.source_readings(comparison=comparison)
    assert error.value.reason == "invalid_canping_text_source"


@pytest.mark.parametrize("comparison", [False, True])
def test_actual_calculation_rejects_unreviewed_text_before_unrelated_projection(
    comparison, monkeypatch, tmp_path, rest, capsys
):
    replace_source(monkeypatch, tmp_path, comparison, "literal")
    response, code, cli, mcp = run_three(
        SPECS["canping"],
        dict(
            date="2024-03-28",
            time="09:00",
            zone="UTC",
            gender="男",
            use_true_solar_time=False,
        ),
        ["analysis_type"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "numerology_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["code"] == (
            "invalid_canping_witness_collation"
            if comparison
            else "invalid_canping_text_collation"
        )


def test_invalid_user_lookup_remains_distinct_from_invalid_source(monkeypatch):
    def must_not_read(*args, **kwargs):
        pytest.fail("Invalid lookup must be rejected before source access")

    monkeypatch.setattr(texts, "_loaded", must_not_read)
    with pytest.raises(ValueError):
        texts.lookup_record("火", True, "female")
    with pytest.raises(ValueError):
        texts.lookup_record("火", 2434, "unknown")
