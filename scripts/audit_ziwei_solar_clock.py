"""Independent JPL solar labels joined to published HKO dates and real charts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.timezones import parse_timezone_name

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests/data/ziwei_solar_jpl_v1"


def load_reference(
    directory: Path = DIRECTORY,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents = {}
    for name in ("protocol", "manifest"):
        raw = (directory / (name + ".json")).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest()
            != (directory / (name + ".sha256")).read_text().strip()
        ):
            raise ValueError("Solar clock source checksum mismatch: " + name)
        documents[name] = json.loads(raw)
    protocol, manifest = documents["protocol"], documents["manifest"]
    if (
        manifest["protocol_sha256"]
        != (directory / "protocol.sha256").read_text().strip()
    ):
        raise ValueError("Solar clock manifest belongs to a different protocol")
    sites = {site["id"]: site for site in protocol["sites"]}
    expected_keys = {
        (s["id"], instant) for s in sites.values() for instant in s["instants"]
    }
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for reply in manifest["replies"]:
        raw = (directory / reply["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != reply["sha256"]:
            raise ValueError("Solar clock reply checksum mismatch: " + reply["path"])
        response = json.loads(raw)
        if "error" in response:
            raise ValueError("Solar clock reply contains an error")
        text, site = response["result"], sites[reply["site_id"]]
        params = reply["request_parameters"]
        wanted_tlist = " ".join(
            "'" + datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M:%S") + "'"
            for s in reply["instants"]
        )
        if params["TLIST"] != wanted_tlist or reply["request_url"] != protocol[
            "source_url"
        ] + "?" + urlencode(params):
            raise ValueError(
                "Solar clock request URL or time list differs from receipt"
            )
        if any(
            params[k] != v
            for k, v in {
                "COMMAND": "'10'",
                "CENTER": "'coord@399'",
                "QUANTITIES": "'34,42,49'",
                "TIME_TYPE": "'UT'",
                "APPARENT": "'AIRLESS'",
                "CAL_TYPE": "'GREGORIAN'",
                "SITE_COORD": f"'{site['longitude']},{site['latitude']},0'",
            }.items()
        ):
            raise ValueError("Solar clock request parameters differ from protocol")
        geo = re.search(
            r"Center geodetic\s*:\s*([-+\d.eE]+),\s*([-+\d.eE]+),\s*([-+\d.eE]+)", text
        )
        if (
            not geo
            or abs((float(geo[1]) - site["longitude"] + 180) % 360 - 180) > 1e-6
            or abs(float(geo[2]) - site["latitude"]) > 1e-6
            or abs(float(geo[3])) > 1e-6
        ):
            raise ValueError("Solar clock reply uses a different observer site")
        for required in (
            "Target body name: Sun (10)",
            "{source: DE441}",
            "Atmos refraction: NO (AIRLESS)",
            "L_Ap_SOL_Time",
            "L_Ap_Hour_Ang",
            "UT1-UTC",
        ):
            if required not in text:
                raise ValueError(
                    "Solar clock reply lacks required declaration: " + required
                )
        table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        found = []
        for raw_row in csv.reader(io.StringIO(table)):
            if len(raw_row) != 7:
                raise ValueError("Unexpected solar clock columns")
            instant = datetime.strptime(
                raw_row[0].strip(), "%Y-%b-%d %H:%M:%S.%f"
            ).replace(tzinfo=timezone.utc)
            key = (site["id"], instant.isoformat())
            if key in rows:
                raise ValueError("Duplicate solar clock source instant")
            apparent, hour_angle, dut1 = (float(raw_row[i]) for i in (3, 4, 5))
            if (
                not all(math.isfinite(v) for v in (apparent, hour_angle, dut1))
                or not 0 <= apparent < 24
            ):
                raise ValueError("Invalid or unavailable solar clock source value")
            if abs(((apparent - hour_angle - 12 + 12) % 24 - 12) * 3600) > 0.00001:
                raise ValueError("JPL solar time and Sun hour angle do not agree")
            mean_label = instant.replace(tzinfo=None) + timedelta(
                seconds=site["longitude"] * 240 + dut1
            )
            mean_seconds = (
                mean_label
                - mean_label.replace(hour=0, minute=0, second=0, microsecond=0)
            ).total_seconds()
            delta = (apparent * 3600 - mean_seconds + 43200) % 86400 - 43200
            label = mean_label + timedelta(seconds=delta)
            rows[key] = dict(
                site=site,
                instant=instant,
                reference_label=label,
                dut1=dut1,
                apparent_hours=apparent,
                hour_angle=hour_angle,
            )
            found.append(instant.isoformat())
        if set(found) != set(reply["instants"]) or len(found) != len(reply["instants"]):
            raise ValueError("Solar clock reply has missing or extra instants")
    if set(rows) != expected_keys or len(rows) != protocol["expected_source_points"]:
        raise ValueError("Solar clock corpus has missing or extra selected points")
    return protocol, [rows[key] for key in sorted(rows)]


def audit_solar_clock(
    hko_reader: Callable[..., list[dict[str, Any]]],
    fixtures: Path,
    directory: Path = DIRECTORY,
) -> dict[str, Any]:
    protocol, rows = load_reference(directory)
    manifest = json.loads((fixtures / "calendar_manifest.json").read_text())
    sources = {s["year"]: s for s in manifest["sources"]}
    tables: dict[int, dict[str, Any]] = {}

    def lunar(label: datetime) -> dict[str, Any]:
        year = label.year
        if year not in tables:
            source = sources[year]
            raw = (fixtures / source["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError("HKO solar-clock date checksum mismatch")
            tables[year] = {
                r["solar"].isoformat(): r
                for r in hko_reader(raw.decode("utf-8-sig"), year)
            }
        value = tables[year][label.date().isoformat()]
        if value["month"] is None or value["is_leap"] is None:
            raise ValueError("Solar clock comparison needs a complete HKO date")
        return dict(
            year=value["year"],
            month=value["month"],
            day=value["day"],
            is_leap_month=value["is_leap"],
        )

    differences, receipts, unresolved = [], [], []
    errors, adjusted_errors = [], []
    for row in rows:
        site, instant, expected = row["site"], row["instant"], row["reference_label"]
        civil = instant.astimezone(parse_timezone_name(site["timezone"])).replace(
            tzinfo=None
        )
        if civil.second or civil.microsecond:
            raise ValueError(
                "Source instant cannot be represented by minute-resolution birth input"
            )
        inputs = dict(
            birth_year=civil.year,
            birth_month=civil.month,
            birth_day=civil.day,
            birth_hour=civil.hour,
            birth_minute=civil.minute,
            birth_timezone=site["timezone"],
            birth_longitude=site["longitude"],
            use_true_solar_time=True,
            gender="男",
        )
        seconds = (
            expected - expected.replace(hour=0, minute=0, second=0, microsecond=0)
        ).total_seconds()
        hour_margin = min(abs(seconds - b) for b in range(3600, 86400, 7200))
        date_margin = min(seconds, 86400 - seconds)
        near_boundary = min(hour_margin, date_margin) < protocol["tolerance_seconds"]
        if near_boundary:
            unresolved.append(
                dict(
                    site=site["id"],
                    instant=instant.isoformat(),
                    distance_seconds=min(hour_margin, date_margin),
                )
            )
        expected_hour = "子丑寅卯辰巳午未申酉戌亥"[((expected.hour + 1) // 2) % 12]
        expected_lunar = lunar(expected)
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            result = calculate_ziwei_birth(
                create_person_info(**inputs), rule_profile=profile
            )
            chart = result["ziwei_birth"]
            receipt = chart["calendar_basis"]["time_input"]
            actual = civil + timedelta(seconds=receipt["applied_delta_seconds"])
            error = (actual - expected).total_seconds()
            adjusted = error + row["dut1"]
            checks = dict(
                clock_within_predeclared_tolerance=abs(error)
                <= protocol["tolerance_seconds"],
                actual_hour=chart["hour_branch"] == expected_hour,
                solar_date=actual.date() == expected.date(),
                lunar_date=chart["lunar_date"] == expected_lunar,
                components_applied=receipt["applied"]
                and receipt["components_computed"],
            )
            # A flagged boundary is never called certified even if the point matches.
            if not all(checks.values()):
                differences.append(
                    dict(
                        site=site["id"],
                        instant=instant.isoformat(),
                        profile=profile,
                        error_seconds=error,
                        checks=checks,
                        reference_boundary_unresolved=near_boundary,
                    )
                )
            errors.append(abs(error))
            adjusted_errors.append(abs(adjusted))
            receipts.append(
                dict(
                    site=site["id"],
                    instant=instant.isoformat(),
                    profile=profile,
                    reference_solar_label=expected.isoformat(),
                    actual_solar_label=actual.isoformat(),
                    error_seconds=error,
                    dut1_adjusted_error_seconds=adjusted,
                    expected_hour=expected_hour,
                    actual_hour=chart["hour_branch"],
                    discrete_boundary_resolved=not near_boundary,
                )
            )
    return dict(
        method_id=protocol["method_id"],
        independent_jpl_points=len(rows),
        profiles_checked=2,
        chart_checks=len(receipts),
        nonboundary_chart_checks=len(receipts) - len(unresolved) * 2,
        near_boundary_chart_checks=len(unresolved) * 2,
        observer_sites=len(protocol["sites"]),
        tolerance_seconds=protocol["tolerance_seconds"],
        max_absolute_error_seconds=max(errors),
        max_dut1_adjusted_absolute_error_seconds=max(adjusted_errors),
        unresolved_discrete_boundary_points=unresolved,
        receipts=receipts,
        differences=differences,
        historical_timezone_certified=False,
        original_astrological_clock_policy_certified=False,
        full_calendar_acceptance_passed=False,
        scope="Finite topocentric JPL solar-clock comparison and HKO date-label integration; both profiles share the same solar normalizer, so 898 charts are not 898 independent celestial observations",
    )
