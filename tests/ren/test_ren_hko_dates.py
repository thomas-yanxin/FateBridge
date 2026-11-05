"""Published dates keep their scope, disagreements and same-instant anchors."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics import hko_term_dates as domain
from fatebridge.core.output_chinese import RenTermDependency
from fatebridge.core.output_ren_term_dates import (
    RenPublishedDateReference,
    require_complete_published_dates,
)
from scripts.astronomy.build_hko_term_dates import build, encoded
from scripts.ren.audit_ren_hko_dates import CORPUS, reference
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
REF = reference()
CASES = json.loads((CORPUS / "protocol.json").read_text())["old_exposed_date_failures"]
INPUTS = [
    (1912, 11, 22),
    (1913, 9, 23),
    (1917, 12, 7),
    (1927, 9, 8),
    (1928, 6, 21),
    (1979, 1, 20),
    (2084, 3, 19),
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def payload(key, index=5):
    y, m, d = INPUTS[index]
    p = dict(
        analysis_year=y,
        analysis_month=m,
        analysis_day=d,
        analysis_hour=23,
        analysis_minute=59,
        analysis_second=0,
        analysis_timezone="Etc/GMT-8",
        use_true_solar_time=False,
        is_diurnal=True,
    )
    if key == "jinkou":
        p["di_fen"] = "酉"
    if key == "liureng_runyear":
        p.update(
            birth_year=1950,
            birth_month=8,
            birth_day=23,
            birth_hour=14,
            birth_timezone="Asia/Shanghai",
            gender="女",
        )
    return p


def raw(key="liureng_gods"):
    s = SPECS[key]
    fn, args, kw = s.bind(s.request_model.model_validate(payload(key)))
    return fn(*args, **kw)


def test_catalogue_reproduces_all200_pinned_sources_without_calculator_answers():
    assert (
        encoded(build())
        == (CORPUS / "catalogue.json").read_bytes()
        == (ROOT / "src/fatebridge/data/astronomy/hko-term-dates-v1.json").read_bytes()
    )
    assert len(REF["terms"]) == 4800 and REF["independent_new_observations"] == 0
    assert {int(k.split(":")[0]) for k in REF["terms"]} == set(range(1901, 2101))
    assert len(CASES) == 7


@pytest.mark.parametrize("fault", ["edit", "refreeze", "extra", "remove"])
def test_reference_denominators_and_labels_cannot_be_changed(fault, tmp_path):
    p = tmp_path / "corpus"
    shutil.copytree(CORPUS, p)
    if fault == "edit":
        with (p / "catalogue.json").open("ab") as f:
            f.write(b" ")
    elif fault == "refreeze":
        (p / "freeze.json").write_text("{}")
    elif fault == "extra":
        (p / "extra").write_text("")
    else:
        (p / "protocol.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(p)


def test_runtime_reference_corruption_fails_without_using_unchecked_labels(
    tmp_path, monkeypatch
):
    p = tmp_path / "data/astronomy"
    p.mkdir(parents=True)
    (p / "hko-term-dates-v1.json").write_text("{}")
    monkeypatch.setattr(domain, "files", lambda _: tmp_path)
    domain._catalogue.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="散列"):
            domain.published_date_reference(
                "小寒", datetime(2026, 1, 5, tzinfo=timezone.utc)
            )
    finally:
        domain._catalogue.cache_clear()


@pytest.mark.parametrize("year", [1800, 1900, 2101, 2200])
def test_outside_years_stay_unknown_rather_than_false_or_true(year):
    r = domain.published_date_reference(
        "小寒", datetime(year, 1, 5, tzinfo=timezone.utc)
    )
    assert r["status"] == "outside_published_range" and r["dates_equal"] is None
    assert r["published_date"] is r["source_url"] is r["source_sha256"] is None
    assert r["instant_accuracy_certified"] is False
    RenPublishedDateReference.model_validate(r)


def test_reference_year_and_day_use_fixed08_not_analysis_zone_or_true_solar_label():
    m = datetime(1927, 9, 8, 16, 5, tzinfo=timezone.utc)
    r = domain.published_date_reference("白露", m)
    for h in [-12, -5, 8, 14]:
        assert (
            domain.published_date_reference(
                "白露", m.astimezone(timezone(timedelta(hours=h)))
            )
            == r
        )
    assert (
        r["computed_hko_date"] == "1927-09-09"
        and r["published_date"] == "1927-09-08"
        and r["dates_equal"] is False
    )
    boundary = domain.published_date_reference(
        "小寒", datetime(1900, 12, 31, 16, tzinfo=timezone.utc)
    )
    assert boundary["hko_year"] == 1901 and boundary["published_date"] is not None
    end = domain.published_date_reference(
        "冬至", datetime(2100, 12, 31, 18, tzinfo=timezone.utc)
    )
    assert end["hko_year"] == 2101 and end["dates_equal"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "date_match"),
        ("dates_equal", True),
        ("dates_equal", 0),
        ("published_date", "1979-01-20"),
        ("source_sha256", "wrong"),
        ("source_url", "wrong"),
        ("catalogue_sha256", "wrong"),
        ("computed_hko_date", "1979-01-21"),
        ("hko_year", 1980),
        ("instant_accuracy_certified", True),
        ("instant_accuracy_certified", 0),
    ],
)
def test_reference_cannot_contradict_its_present_term_and_instant(field, value):
    r = domain.published_date_reference(
        "大寒", datetime.fromisoformat("1979-01-20T15:59:54+00:00")
    )
    r[field] = value
    with pytest.raises(ValidationError):
        RenPublishedDateReference.model_validate(r)


def test_partial_reference_checks_only_copresent_facts_but_dependency_anchor_cannot_be_spliced():
    RenPublishedDateReference.model_validate(dict(status="date_mismatch"))
    r = domain.published_date_reference(
        "大寒", datetime.fromisoformat("1979-01-20T15:59:54+00:00")
    )
    RenTermDependency.model_validate(
        dict(
            name="大寒",
            civil_moment="1979-01-20T15:59:54+00:00",
            published_date_reference=r,
        )
    )
    with pytest.raises(ValidationError):
        RenTermDependency.model_validate(
            dict(
                name="小寒",
                civil_moment="1979-01-20T15:59:54+00:00",
                published_date_reference=r,
            )
        )


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "status", "zero", "name", "scope"]
)
def test_full_policy_cannot_drop_or_forge_reference_evidence(fault):
    p = raw()["liureng"]["calendar_policy"]
    r = p["solar_term_dependencies"][1]
    if fault == "missing":
        r.pop("published_date_reference")
    elif fault == "duplicate":
        p["solar_term_dependencies"].append(copy.deepcopy(r))
    elif fault == "status":
        r["published_date_reference"]["dates_equal"] = True
    elif fault == "zero":
        r["published_date_reference"]["instant_accuracy_certified"] = 0
    elif fault == "name":
        r["name"] = "春分"
    else:
        r["published_date_reference"]["comparison_scope"] = "full_calendar_certified"
    with pytest.raises(ValueError):
        require_complete_published_dates(p)


@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
@pytest.mark.parametrize("index", range(7))
def test_old_seven_date_disagreements_survive_all_three_protocols(
    key, index, rest, tmp_path, capsys
):
    s = SPECS[key]
    p = payload(key, index)
    prefix = "jinkou" if key == "jinkou" else "liureng"
    fields = evidence_views(s)["published_term_dates"]["fields"]
    opts = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        s.rest_path,
        json=p,
        params=[
            *[("fields", f) for f in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        s,
        p,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    mcp = asyncio.run(native(s, p, **opts))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    assert business(http.json()) == business(cli) == business(mcp.structured_content)
    terms = http.json()[prefix]["calendar_policy"]["solar_term_dependencies"]
    source = CASES[index]
    row = next(r for r in terms if r["name"] == source["term"])
    r = row["published_date_reference"]
    assert (
        r["published_date"] == source["published_date"]
        and r["dates_equal"] is False
        and r["status"] == "date_mismatch"
        and r["instant_accuracy_certified"] is False
    )
    require_complete_published_dates(http.json()[prefix]["calendar_policy"])


def test_runyear_snapshot_shows_same_dependency_conflict_and_reference_scope():
    result = raw("liureng_runyear")
    text = result["snapshot_text"]
    p = result["liureng"]["calendar_policy"]
    assert "香港天文台逐日表仅核对固定UTC+08日期" in text and "日期不一致" in text
    r = next(r for r in p["solar_term_dependencies"] if r["name"] == "大寒")[
        "published_date_reference"
    ]
    assert (
        f"计算+08日期{r['computed_hko_date']}；天文台刊载{r['published_date']}；日期不一致"
        in text
    )
    require_complete_published_dates(p)


@pytest.mark.parametrize("project", [False, True])
def test_three_protocols_reject_deleted_or_changed_reference_before_projection(
    project, rest, monkeypatch, tmp_path, capsys
):
    s = SPECS["liureng_gods"]
    p = payload("liureng_gods")
    bad = raw()
    bad["liureng"]["calendar_policy"]["solar_term_dependencies"][0].pop(
        "published_date_reference"
    )
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == s.key:
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    opts = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        opts = dict(fields=["four_pillars"], strict_fields=True)
    h = rest.post(s.rest_path, json=p, params=params)
    m = asyncio.run(native(s, p, **opts))
    code, c = call_cli(s, p, tmp_path, capsys, flags=flags)
    assert h.status_code == 500 and m.is_error and code != 0
    assert all(
        v["error_code"] == "internal_error" and "liureng" not in v
        for v in [h.json(), m.structured_content, c]
    )


def test_same_published_day_does_not_claim_the_synthetic_noon_is_a_solar_root():
    # Deliberately hypothetical noon: the reference predicate certifies no instant.
    r = domain.published_date_reference(
        "大寒", datetime.fromisoformat("1979-01-21T12:00:00+08:00")
    )
    assert r["dates_equal"] is True and r["status"] == "date_match"
    assert r["instant_accuracy_certified"] is False


@pytest.mark.parametrize("year", [1800, 2200])
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_valid_public_year_outside_hko_keeps_calculation_and_unknown_reference(
    year, key
):
    s = SPECS[key]
    p = payload(key)
    p["analysis_year"] = year
    fn, args, kw = s.bind(s.request_model.model_validate(p))
    result = fn(*args, **kw)
    assert "error" not in result
    prefix = "jinkou" if key == "jinkou" else "liureng"
    policy = result[prefix]["calendar_policy"]
    require_complete_published_dates(policy)
    assert all(
        r["published_date_reference"]["status"] == "outside_published_range"
        and r["published_date_reference"]["dates_equal"] is None
        for r in policy["solar_term_dependencies"]
    )
    assert "超出官方1901—2100逐日表范围，未比较" in result["snapshot_text"]
