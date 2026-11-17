"""Independent exact arithmetic over predeclared clauses and source readings."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

import flint
from flint import fmpq

P = Path(__file__).parent
spec = json.loads((P / "arithmetic-inputs.json").read_text())
reading = json.loads((P / "additional-source-reading-frozen.json").read_text())
assert (
    hashlib.sha256(
        (P / "additional-source-reading-frozen.json").read_bytes()
    ).hexdigest()
    == spec["additional_reading_sha256"]
)
assert not (P / "reference.json.gz").exists()
numerals = [
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
    "二十一",
    "二十二",
    "二十三",
    "二十四",
    "二十五",
    "二十六",
    "二十七",
    "二十八",
    "二十九",
    "三十",
]
numbers = {label: index for index, label in enumerate(numerals, 1)}


def source_label(text, inherited):
    if "年" in text:
        year_text, text = text.split("年")
        year = numbers[year_text]
        marker = year
    else:
        assert inherited is not None
        year, marker = inherited, None
    month_text, day_text = text.split("月")
    month = 1 if month_text == "正" else numbers[month_text]
    day = numbers[day_text[1:] if day_text.startswith("初") else day_text]
    assert 1 <= month <= 12 and 1 <= day <= 30
    return (
        (year, month, day),
        marker,
        fmpq(360) * (year - 1) + fmpq(30) * (month - 1) + (day - 1),
    )


def label_for(day):
    years = (day / 360).floor()
    in_year = day - years * 360
    months = (in_year / 30).floor()
    in_month = in_year - months * 30
    whole = in_month.floor()
    return {
        "ordinal_year": int(years) + 1,
        "month": int(months) + 1,
        "day": int(whole) + 1,
        "fraction_of_nominal_day_exact": str(in_month - whole),
        "calendar": "local_limit_ordinal_12_months_30_days",
    }


rows = []
cell_rows = []
audits = []
epsilon = fmpq(spec["samples"]["epsilon"])
integer_rows = 0
for group in spec["groups"]:
    name = group["group"]
    span = group["months"] * 30 + group["days"]
    total = 30 * span
    annual = fmpq(group["annual_rate"])
    duration = fmpq(group["duration_years"])
    context = None
    literals = []
    for column, text in enumerate(reading["groups"][name], 1):
        left, right = text.split("|")
        start_label, start_marker, start = source_label(left, context)
        last_label, last_marker, last = source_label(right, start_label[0])
        context = last_label[0]
        assert last >= start
        end = last + 1
        literals.append((column, start, end))
        formula_start, formula_end = fmpq((column - 1) * span), fmpq(column * span)
        cell_rows.append(
            {
                "group": name,
                "column": column,
                "literal_text": text,
                "literal_start_exact": str(start),
                "literal_end_exclusive_exact": str(end),
                "explicit_start_year": start_marker,
                "explicit_last_year": last_marker,
                "formula_start_exact": str(formula_start),
                "formula_end_exclusive_exact": str(formula_end),
                "formula_start_label": label_for(formula_start),
                "formula_last_label": label_for(formula_end - 1),
                "formula_end_exclusive_label": label_for(formula_end),
                "literal_minus_formula_start_exact": str(start - formula_start),
                "literal_minus_formula_end_exact": str(end - formula_end),
            }
        )
    points = {fmpq(day) for day in range(total + 1)}
    integer_rows += total + 1
    for boundary in [fmpq(i * span) for i in range(31)] + [
        value for _, start, end in literals for value in (start, end)
    ]:
        for sample in (boundary - epsilon, boundary + epsilon):
            if 0 <= sample <= total:
                points.add(sample)
    for column in range(30):
        for offset in spec["samples"]["fractional_offsets"]:
            points.add(fmpq(column * span) + fmpq(offset))
    for day in sorted(points):
        degree = day / span
        matches = [column for column, start, end in literals if start <= day < end]
        literal_end = max(end for _, _, end in literals)
        status = (
            "at_printed_limit_end"
            if day == literal_end
            else (
                "unique_literal_cell"
                if len(matches) == 1
                else (
                    "unassigned_printed_gap"
                    if not matches
                    else "ambiguous_printed_overlap"
                )
            )
        )
        printed_degree = day * annual / 360
        rows.append(
            {
                "group": name,
                "elapsed_nominal_days_exact": str(day),
                "nominal_source_date": label_for(day),
                "formula_degrees_exact": str(degree),
                "printed_annual_degrees_exact": str(printed_degree),
                "monthday_minus_printed_annual_exact": str(degree - printed_degree),
                "formula_cell": None if day == total else int(degree.floor()) + 1,
                "formula_status": (
                    "local_limit_complete" if day == total else "within_local_limit"
                ),
                "literal_matching_cells": matches,
                "literal_status": status,
                "literal_selected_cell": matches[0] if len(matches) == 1 else None,
            }
        )
    audits.append(
        {
            "group": name,
            "days_per_degree": span,
            "monthday_annual_rate_exact": str(fmpq(360, span)),
            "annual_rate_agrees": fmpq(360, span) == annual,
            "printed_full_limit_degrees_exact": str(annual * duration),
            "printed_full_limit_minus30_exact": str(annual * duration - 30),
            "monthday_limit_minus_source_duration_days_exact": str(
                fmpq(total) - duration * 360
            ),
        }
    )
assert integer_rows == spec["samples"]["integer_expected_rows"] == 21787
assert len(cell_rows) == 210
assert not any(
    name == "fatebridge" or name.startswith("fatebridge.") for name in sys.modules
)
result = {
    "method": "flint_fmpq_exact_nominal_ruler_v1",
    "python_flint_version": flint.__version__,
    "flint_version": str(flint.__FLINT_VERSION__),
    "production_imported": False,
    "python_fractions_module_imported_by_dependency": "fractions" in sys.modules,
    "python_fractions_arithmetic_used_by_oracle": False,
    "dependency_note": "FLINT fmpq hashing imports fractions when building exact-rational sample sets. Reference calculations use fmpq only; the oracle never imports Fraction or FateBridge. The overly strict first module-import assertion failed and is preserved in oracle-attempt-1.",
    "inputs_sha256": hashlib.sha256(
        (P / "arithmetic-inputs.json").read_bytes()
    ).hexdigest(),
    "reading_sha256": spec["additional_reading_sha256"],
    "integer_nominal_day_rows": integer_rows,
    "total_rows": len(rows),
    "cell_rows": cell_rows,
    "audits": audits,
    "rows": rows,
    "date_only_stress": [
        {
            "elapsed_nominal_days_exact": value,
            "nominal_source_date": label_for(fmpq(value)),
        }
        for value in spec["samples"]["date_only_stress"]
    ],
    "scope": "Exact formal arithmetic for the declared12by30 nominal model and given source strings. Additional same-witness reading is not independent expert adjudication. No civil/birth/physical/predictive acceptance.",
}
blob = json.dumps(
    result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
).encode()
(P / "reference.json.gz").write_bytes(gzip.compress(blob, mtime=0))
files = [
    "arithmetic-inputs.json",
    "additional-source-reading-frozen.json",
    "generate_reference.py",
    "reference.json.gz",
]
(P / "reference-before-production-comparison-sha256.json").write_text(
    json.dumps(
        {name: hashlib.sha256((P / name).read_bytes()).hexdigest() for name in files},
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
print(
    json.dumps(
        {
            "integer_nominal_day_rows": integer_rows,
            "all_rational_rows": len(rows),
            "cell_rows": len(cell_rows),
            "python_flint_version": flint.__version__,
            "flint_version": str(flint.__FLINT_VERSION__),
            "formula_literal_endpoint_disagreements": sum(
                row["literal_minus_formula_start_exact"] != "0"
                or row["literal_minus_formula_end_exact"] != "0"
                for row in cell_rows
            ),
            "annual_monthday_rate_contradictions": sum(
                not row["annual_rate_agrees"] for row in audits
            ),
        },
        indent=2,
    )
)
