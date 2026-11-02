"""Compare complete frozen publisher labels without making UT into UTC."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_solar_reference import parse_solar_reference_datetime

from .meihua_solar_seconds import parse_naoj_minute_label

YEARS = range(1900, 2101)
EXPECTED_REFERENCE_SHA256 = (
    "d5692771ab8b96cb56df322a40ac1ea2afb4f4930ee8bc14bfb2878bcb69c233"
)
_URL = "https://eco.mtk.nao.ac.jp/cgi-bin/koyomi/cande/phenomena_sy.cgi"
_PARAMETERS = [
    ["lst", "8"],
    ["lsti", "8"],
    ["phenom", "50"],
    ["cal", "0"],
    ["jg", "2"],
    ["dtm", "0"],
    ["dt", "0"],
    ["body", "0"],
    ["body", "1"],
    ["coord", "1"],
    ["figure", "0"],
]
_NAMES = tuple(
    "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 "
    "小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
)
_JAPANESE_NAMES = tuple(
    "小寒 大寒 立春 雨水 啓蟄 春分 清明 穀雨 立夏 小満 芒種 夏至 "
    "小暑 大暑 立秋 処暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate reference JSON keys")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            assert self.row is not None
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_annual_response(
    raw: bytes, receipt: dict[str, Any], year: int
) -> list[dict[str, Any]]:
    """Check the submitted identity and the actually returned year/time basis."""
    if (
        not isinstance(receipt, dict)
        or type(year) is not int
        or year not in YEARS
        or receipt.get("url") != _URL
        or receipt.get("method") != "POST"
        or receipt.get("parameters") != [["year", str(year)], *_PARAMETERS]
        or receipt.get("encoding") != "euc-jp"
        or receipt.get("production_imports") is not False
        or receipt.get("response_sha256") != _sha(raw)
    ):
        raise ValueError("NAOJ query identity or response bytes differ")
    page = _Page()
    page.feed(raw.decode("euc-jp"))
    visible = "".join(page.text)
    header = re.search(r"標準時:UT\+8h\s*ΔＴ＝(.+?)1582年", visible)
    version = re.search(r"\(ver\.([0-9A-Za-z.]+)\)", visible)
    if f"{year}年の天象" not in visible or header is None or version is None:
        raise ValueError("Returned year or UT+8/Delta T header differs")
    rows = [r for r in page.rows if r and r[0].startswith(f"{year}/")]
    if len(rows) != 24 or rows != receipt.get("rows"):
        raise ValueError("Retain exactly the 24 actually returned annual rows")
    result = []
    for index, row in enumerate(rows):
        expected_name = f"{_JAPANESE_NAMES[index]}(黄経{(285 + 15 * index) % 360}°)"
        if (
            len(row) != 6
            or row[2:5] != ["太陽", "二十四節気", ""]
            or row[5] != expected_name
        ):
            raise ValueError("Solar term identity, order or longitude differs")
        normalized = parse_naoj_minute_label(row[0], row[1])
        result.append(
            {
                "year": year,
                "index": index,
                "term": _NAMES[index],
                "source_name": _JAPANESE_NAMES[index],
                "longitude": (285 + 15 * index) % 360,
                "raw_date_label": row[0],
                "raw_clock_label": row[1],
                "label_normalization": normalized,
                "source_midnight_label": row[1] in {"00:00", "24:00"},
                "source": {
                    "publisher": "国立天文台 / NAOJ",
                    "attribution": "(C) 国立天文台 / NAOJ",
                    "url": _URL,
                    "query_parameters": receipt["parameters"],
                    "response_sha256": _sha(raw),
                    "retrieved_at": receipt["at"],
                    "standard_time": "UT+8h",
                    "delta_t_header": header.group(1).strip(),
                    "delta_t_header_is_exact_per_event_TT_minus_UTC": False,
                    "version": version.group(1),
                    "kind": "online_theoretical_calculation_not_physical_observation",
                    "UTC_epoch_authenticated": False,
                    "rounding_rule_authenticated": False,
                },
            }
        )
    return result


def read_naoj_reference(
    directory: Path, *, expected_sha256: str = EXPECTED_REFERENCE_SHA256
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require the full 201-year commitment before any production calculation."""
    directory = directory.resolve()
    manifest_raw = (directory / "manifest.json").read_bytes()
    if (
        not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or _sha(manifest_raw) != expected_sha256
    ):
        raise ValueError("NAOJ reference manifest differs from its prior commitment")
    manifest = _json(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("Reference manifest must be an object")
    if (
        manifest.get("id") != "meihua_naoj_solar_labels_v1"
        or manifest.get("version") != "1.0.0"
    ):
        raise ValueError("Unknown NAOJ reference identity")
    hashes = manifest.get("files")
    if not isinstance(hashes, dict):
        raise ValueError("Reference requires recorded file hashes")
    required = {
        f"naoj-{year}-default{suffix}"
        for year in YEARS
        for suffix in [".html", ".txt", "-query.json"]
    }
    if not required <= hashes.keys():
        raise ValueError("All201 years and all4824 terms are required")

    def verify() -> None:
        if (directory / "manifest.json").read_bytes() != manifest_raw:
            raise ValueError("Reference manifest changed during its read")
        for name, digest in hashes.items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory) or _sha(path.read_bytes()) != digest:
                raise ValueError(
                    "Frozen reference content changed or escapes its bundle"
                )

    verify()
    rows = []
    for year in YEARS:
        raw = (directory / f"naoj-{year}-default.html").read_bytes()
        receipt = _json((directory / f"naoj-{year}-default-query.json").read_bytes())
        rows.extend(parse_annual_response(raw, receipt, year))
    verify()
    if len(rows) != 4824 or len({(r["year"], r["term"]) for r in rows}) != 4824:
        raise ValueError("A complete unique cohort is required")
    return rows, {
        "manifest_sha256": expected_sha256,
        "annual_queries": 201,
        "solar_terms": 4824,
        "all_frozen_file_hashes_verified": True,
        "source_authenticity_or_independent_dynamics_certified": False,
    }


def compare_label(
    reference: dict[str, Any], actual: dict[str, Any], hko: dict[str, Any]
) -> dict[str, Any]:
    """Compare labels without treating their difference as physical time error."""
    if actual.get("name") != reference["term"]:
        raise ValueError("Actual and reference term identities must match")
    moment = parse_solar_reference_datetime(actual["datetime_with_offset"])
    if moment.utcoffset() is None:
        raise ValueError("The actual returned solar instant requires its offset")
    clock = moment.astimezone(timezone(timedelta(hours=8)))
    label = reference["label_normalization"]["nominal_display_datetime"]
    source_label = datetime.fromisoformat(label)
    difference = (source_label - clock.replace(tzinfo=None)).total_seconds()
    hko_date = hko.get("published_date")
    details = actual.get("solar_model_details") or {}
    return {
        "year": reference["year"],
        "index": reference["index"],
        "term": reference["term"],
        "computed_datetime_at_fixed_UTC8": clock.isoformat(),
        "computed_date_label": clock.date().isoformat(),
        "actual_ephemeris_model": actual.get("ephemeris_model"),
        "actual_civil_time_method": details.get("civil_time_method"),
        "actual_future_leap_assumption": details.get(
            "future_leap_seconds_assumed_unchanged"
        ),
        "NAOJ": reference,
        "HKO_published_date_label": hko_date,
        "HKO_comparison_status": hko["comparison_status"],
        "computed_date_equals_NAOJ_normalized_label": clock.date()
        == source_label.date(),
        "HKO_date_equals_NAOJ_normalized_label": (
            hko_date == source_label.date().isoformat() if hko_date else None
        ),
        "nominal_NAOJ_label_minus_computed_seconds": difference,
        "label_difference_is_instant_error": False,
        "same_time_conversion_authenticated": False,
        "reference_rounding_rule_authenticated": False,
        "source_midnight_requires_extra_care": reference["source_midnight_label"],
        "actual_event_date_certified_from_minute_label": False,
        "actual_error_interval_seconds": None,
    }


def audit_solar_publishers(
    directory: Path, *, expected_sha256: str = EXPECTED_REFERENCE_SHA256
) -> dict[str, Any]:
    reference, receipt = read_naoj_reference(directory, expected_sha256=expected_sha256)
    from fatebridge.core.almanac import SOLAR_TERM_NAMES, get_solar_terms_for_year
    from fatebridge.core.meihua_solar_reference import compare_solar_term_date
    from fatebridge.validation.meihua_runtime_guard import (
        capture_calendar_runtime,
        verify_calendar_runtime,
    )
    from fatebridge.validation.meihua_source_guard import (
        capture_package_sources,
        verify_package_sources,
    )

    package = Path(__file__).resolve().parents[1]
    source = capture_package_sources(package)
    runtime = capture_calendar_runtime()
    rows = []
    models: Counter[str] = Counter()
    for year in YEARS:
        actual = get_solar_terms_for_year(year, "UTC+08:00")
        if len(actual) != 24 or [t.name for t in actual] != list(SOLAR_TERM_NAMES):
            raise ValueError("All24 actual term identities are required per year")
        for index, term in enumerate(actual):
            value = term.as_dict()
            ref = reference[(year - 1900) * 24 + index]
            hko = compare_solar_term_date(value, fact_path=f"year{year}.term{index}")
            rows.append(compare_label(ref, value, hko))
            models[term.ephemeris_model] += 1
    if (
        sum(
            r["HKO_comparison_status"]
            in {"published_date_match", "published_date_disagreement"}
            for r in rows
        )
        != 4800
    ):
        raise ValueError("The full original HKO4800 comparison must remain present")
    read_naoj_reference(directory, expected_sha256=expected_sha256)
    verify_package_sources(package, source)
    verify_calendar_runtime(runtime)
    hko_bad = [
        r for r in rows if r["HKO_comparison_status"] == "published_date_disagreement"
    ]
    naoj_bad = [r for r in rows if not r["computed_date_equals_NAOJ_normalized_label"]]
    between = [r for r in rows if r["HKO_date_equals_NAOJ_normalized_label"] is False]
    return {
        "audit_id": "meihua_full_supported_solar_publisher_labels_v1",
        "reference": receipt,
        "all4824_rows_compared": len(rows) == 4824,
        "original_HKO4800_compared": 4800,
        "original_HKO_date_gate_met": not hko_bad,
        "original_HKO_disagreement_count": len(hko_bad),
        "NAOJ_normalized_label_disagreement_count": len(naoj_bad),
        "HKO_NAOJ_normalized_label_disagreement_count": len(between),
        "source_midnight_label_count": sum(
            r["source_midnight_requires_extra_care"] for r in rows
        ),
        "all_nominal_date_labels_agree": not hko_bad and not naoj_bad and not between,
        "date_disagreements_are_not_automatically_calculation_errors": True,
        "original_TT_one_second_gate_replaced": False,
        "original_HKO_reference_replaced": False,
        "actual_models": dict(models),
        "source_guard": source,
        "runtime_guard": runtime,
        "rows": rows,
        "actual_physical_observations_added": 0,
        "absolute_civil_time_accuracy_established": False,
        "predictive_efficacy_established": False,
        "scope": "Full frozen online publisher labels and actual returned solar instants. UT+8 and default Delta T are preserved.24:00 rolls only the label date. Minute display, quantization, UT/UTC conventions and model uncertainty are not an authenticated physical error bound or a prediction trial.",
    }
