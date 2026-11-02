"""Smoke-test an extracted wheel, with no source-checkout imports.

Run with ``uv run --locked --extra dev python -I scripts/check_sukuyo_wheel.py
--wheel /path/to/fatebridge.whl``. Dependencies come from the uv environment;
FateBridge itself must come from the extracted artifact. This is not a clean
dependency installation, platform CI or deployment acceptance.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not sys.flags.isolated:
        raise SystemExit("Run this script with python -I to isolate import paths")
    if any(n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules):
        raise SystemExit("FateBridge was imported before wheel selection")
    report = {
        "wheel": str(args.wheel.resolve()),
        "sha256": hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
    }
    with tempfile.TemporaryDirectory(prefix="sukuyo-wheel-check-") as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(args.wheel) as archive:
            archive.extractall(stage)
        os.environ.pop("SE_EPHE_PATH", None)
        sys.path.insert(0, str(stage))
        import fatebridge
        from fatebridge.core.sukuyo import calendar_mansion
        from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
        from fatebridge.core.sukuyo_padas import palace_reference, reference_cell
        from fatebridge.services.divination import (
            calculate_sukuyo_compatibility,
            calculate_suzhan_analysis,
        )
        from fatebridge.services.tool_catalog import CATALOG
        from fatebridge.validation.sukuyo import required_quote_paths

        assert Path(fatebridge.__file__).is_relative_to(stage)
        from fatebridge.core import ephemeris_runtime, guolao

        catalogue_bytes = len(os.fsencode(str(guolao.DATA)))
        operator_bytes = max(160, 243 - catalogue_bytes)
        component = "op" + "x" * max(
            1, operator_bytes - len(os.fsencode(str(stage))) - 3
        )
        operator_directory = stage / component
        operator_directory.mkdir()
        assert len(os.fsencode(str(operator_directory))) <= 242
        assert (
            len(os.fsencode(str(guolao.DATA) + os.pathsep + str(operator_directory)))
            > 242
        )
        previous_path = ephemeris_runtime.configured_ephemeris_path()
        try:
            os.environ["SE_EPHE_PATH"] = str(operator_directory)
            ephemeris_runtime.configure_ephemeris_path(str(operator_directory))
            long_path_result = calculate_suzhan_analysis(
                date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
            )
            assert "error" not in long_path_result, long_path_result
            assert len(long_path_result["astronomy"]["boundaries"]) == 28
            assert os.environ["SE_EPHE_PATH"] == str(operator_directory)
        finally:
            os.environ.pop("SE_EPHE_PATH", None)
            ephemeris_runtime.configure_ephemeris_path(previous_path)
        # An installed package path can contain a literal native list delimiter.
        # Verify the artifact's actual lookup, rather than only its helper.
        separator_catalogue = stage / "catalogue;copy"
        separator_catalogue.mkdir()
        for name in ["sefstars.txt", "sources.json"]:
            shutil.copy2(guolao.DATA / name, separator_catalogue / name)
        with patch.object(guolao, "DATA", separator_catalogue):
            separator_result = calculate_suzhan_analysis(
                date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
            )
            assert "error" not in separator_result, separator_result
            assert separator_result["chart"] == long_path_result["chart"]
            assert separator_result["astronomy"] == long_path_result["astronomy"]
        from fatebridge.core import suzhan_astronomy
        from fatebridge.core.astro import runtime as sky_runtime
        from fatebridge.core.astro.birth import build_astro_birth_info

        reference_birth = build_astro_birth_info(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=0,
        )
        baseline_sky = suzhan_astronomy.build_equatorial_mansions(reference_birth)
        catalogue_file = guolao.DATA / "sefstars.txt"
        original_catalogue = catalogue_file.read_bytes()
        altered_catalogue = original_catalogue.replace(
            b"FBJ00,FBJ00,ICRS,13.0,25.0,",
            b"FBJ00,FBJ00,ICRS,13.0,26.0,",
            1,
        )
        assert altered_catalogue != original_catalogue
        native_call = sky_runtime.ephemeris_call
        lookup_count = 0

        def change_catalogue_during_lookup(name, *args, **kwargs):
            nonlocal lookup_count
            if name == "fixstar2":
                lookup_count += 1
                if lookup_count == 1:
                    catalogue_file.write_bytes(altered_catalogue)
                elif lookup_count == 2:
                    catalogue_file.write_bytes(original_catalogue)
            return native_call(name, *args, **kwargs)

        try:
            with patch.object(
                sky_runtime, "ephemeris_call", change_catalogue_during_lookup
            ):
                captured_sky = suzhan_astronomy.build_equatorial_mansions(
                    reference_birth
                )
            assert lookup_count == 28
            assert captured_sky == baseline_sky
        finally:
            catalogue_file.write_bytes(original_catalogue)
        metadata_file = guolao.DATA / "sources.json"
        original_metadata = metadata_file.read_bytes()
        native_positions = suzhan_astronomy.positions

        def change_metadata_after_calculation(*args, **kwargs):
            raw = native_positions(*args, **kwargs)
            metadata_file.write_bytes(original_metadata + b"\n")
            return raw

        try:
            with patch.object(
                suzhan_astronomy, "positions", change_metadata_after_calculation
            ):
                captured_sky = suzhan_astronomy.build_equatorial_mansions(
                    reference_birth
                )
            assert captured_sky == baseline_sky
        finally:
            metadata_file.write_bytes(original_metadata)
        report["native_catalogue_snapshot_and_loaded_metadata_receipt"] = (
            "passed_real_native_A_B_A_and_postcalculation_metadata_change"
        )
        from fatebridge.core.sukuyo_taibai import taibai_direction_reference

        assert taibai_direction_reference(9)["realm"] == "below_ground"
        assert taibai_direction_reference(9)["horizontal_direction"] is None
        taibai = taibai_direction_reference(10)
        assert taibai["location"] == "天上" and taibai["horizontal_direction"] is None
        assert taibai["witnesses"][1]["status"] == "row_deleted_in_apparatus"
        assert taibai["witnesses"][1]["location"] is None
        assert not taibai["physical_venus_position_evaluated"]
        assert not taibai["movement_alignment_evaluated"]
        assert not taibai["applied_to_activity_assessment"]
        assert len(taibai["table_apparatus"]) == 13
        r = calendar_mansion("2025-03-04")
        assert r["natal_su27"] == "毕"
        assert r["mansion_method_id"] == "t1299_lower_fullmoon27_v1"
        basis = "japanese_hutime_1002_1_utc09"
        japanese = calendar_mansion("2017-06-24", zone="+09:00", calendar_basis=basis)
        assert japanese["lunar_month"] == 5 and japanese["is_leap_month"]
        assert japanese["natal_su27"] is None and japanese["candidate_su27s"] == ["参"]
        assert (
            japanese["calendar_reference"]["date_provenance"]
            == "provider_reference_projection_not_whole_jingu_edition_verified"
        )
        assert (
            japanese["calendar_reference"]["source_bundle_sha256"]
            == hashlib.sha256(
                (stage / "fatebridge/data/sukuyo_japanese_daily_v1.json").read_bytes()
            ).hexdigest()
        )
        historical_basis = "japanese_naoj_historical_utc09"
        historical = calendar_mansion(
            "0820-03-22", zone="+09:00", calendar_basis=historical_basis
        )
        assert [
            historical[k]
            for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
        ] == [820, 2, 1, False]
        variant = historical["calendar_reference"]["cross_source_comparison"]
        assert variant["control_fields"] == [820, 1, 30, True]
        assert not variant["control_applied_to_primary"]
        assert historical["natal_su27"] == "奎"
        assert (
            historical["calendar_reference"]["source_bundle_sha256"]
            == hashlib.sha256(
                (
                    stage / "fatebridge/data/sukuyo_japanese_historical_v1.json"
                ).read_bytes()
            ).hexdigest()
        )
        for civil, expected in (("1872-12-30", 1), ("1872-12-31", 2)):
            reform = calendar_mansion(
                civil, zone="+09:00", calendar_basis=historical_basis
            )
            assert reform["lunar_month"] == 12 and reform["lunar_day"] == expected
            assert reform["calendar_reference"]["month_truncated_by_calendar_reform"]
            assert reform["calendar_reference"]["source_month_length_days"] == 2
        try:
            calendar_mansion(
                "1873-01-01", zone="+09:00", calendar_basis=historical_basis
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Old-lunisolar reference continued beyond the legal reform"
            )
        early = calendar_mansion(
            "0001-01-01", zone="+15:00", calendar_basis=historical_basis
        )
        assert early["calendar_backend"] == "frozen_naoj_historical_month_starts"
        assert early["out_of_range_calendar_dates"] == ["0000-12-31"]
        assert early["natal_su27"] is None and not early["birth_time_known"]
        assert early["date_support"]["utc_endpoints_use_astronomical_year_numbering"]
        documentary = calendar_mansion(
            "0903-07-13", "00:00:00", "+09:00", calendar_basis=historical_basis
        )
        day_reference = documentary["calendar_reference"]["day_ganzhi_reference"]
        assert day_reference["name"] == "庚辰"
        assert day_reference["reference_boundary"] == "fixed_utc09_civil_midnight"
        assert not day_reference["bazi_day_pillar_evaluated"]
        assert not day_reference["historical_day_boundary_accepted"]
        halves = [
            calendar_mansion(
                "0806-09-20",
                zone="+09:00",
                calendar_basis=historical_basis,
                calendar_profile="hinoo_t1299_host27",
                calendar_day_part=part,
            )["natal_su27"]
            for part in ("first_half", "second_half")
        ]
        assert halves == ["轸", "角"]
        edge = calendar_mansion("2031-01-22", zone="UTC", calendar_basis=basis)
        assert edge["out_of_range_calendar_dates"] == ["2031-01-23"]
        assert edge["natal_su27"] is None
        repeated_japanese = calendar_mansion(
            "1969-09-30", zone="Pacific/Kwajalein", calendar_basis=basis
        )
        assert len(repeated_japanese["calendar_candidates"]) == 3
        skies = [
            calculate_suzhan_analysis(
                date="2017-06-24",
                time="12:00:00",
                zone="+09:00",
                szchart=1,
                calendar_basis=b,
            )
            for b in ["chinese_hko_utc08", basis]
        ]
        assert all("error" not in value for value in skies), skies
        assert (
            skies[0]["chart"] == skies[1]["chart"]
            and skies[0]["astronomy"] == skies[1]["astronomy"]
        )
        from fatebridge.core.sukuyo import day_evidence

        monday = calendar_mansion("2025-03-03")
        gathering = day_evidence(
            monday, activity="social", activity_details=["social_gathering"]
        )
        friendship = day_evidence(
            monday, activity="social", activity_details=["forming_friendship"]
        )
        assert gathering["activity_assessment"]["evidence_status"] == "favorable"
        assert friendship["activity_assessment"]["evidence_status"] == "caution"
        departure = day_evidence(
            monday, activity="travel", activity_details=["personal_departure"]
        )
        private = day_evidence(
            monday, activity="travel", activity_details=["private_journey"]
        )
        matched = lambda value: {
            r["rule_id"] for r in value["activity_assessment"]["matched_rules"]
        }
        assert "t1299_lower_method_weekday_03" not in matched(departure)
        assert "t1299_lower_method_weekday_03" in matched(private)
        sunday = calendar_mansion("2025-03-02")
        tourist = day_evidence(
            sunday, activity="travel", activity_details=["long_distance_journey"]
        )
        official = day_evidence(
            sunday,
            activity="travel",
            activity_details=["long_distance_journey", "royal_or_official_traveler"],
        )
        assert "t1299_activity_20" in matched(tourist)
        assert "t1299_lower_method_weekday_01" not in matched(tourist)
        assert "t1299_lower_method_weekday_01" in matched(official)
        from fatebridge.core.sukuyo import SU27_ORDER
        from fatebridge.core.sukuyo_profiles import fullmoon_calculation
        from fatebridge.core.sukuyo_profiles import source_bundle as profile_sources

        exposed_profile = profile_sources()
        exposed_profile["fullmoon_anchors"][0]["fullmoon_mansion"] = "角"
        assert fullmoon_calculation(1, 15, SU27_ORDER)["direct_mansion"] == "翼"
        first_night = calendar_day_evidence(1)
        eleventh_night = calendar_day_evidence(11)
        assert first_night["time_restrictions"] == []
        assert not first_night["prose_verse_time_semantic_conflict"]
        assert len(eleventh_night["time_restrictions"]) == 5
        assert (
            eleventh_night["verse_abbreviation_resolution"]["interpreted_lunar_day"]
            == 11
        )
        foreign = calculate_sukuyo_compatibility(
            person1_date="2025-01-29", person1_zone="UTC", person2_date="2025-03-04"
        )
        assert foreign["status"] == "partial" and foreign["pair"] is None
        assert foreign["person1"]["calendar"]["input_datetime"] is None
        assert foreign["person1"]["calendar"]["candidate_su27s"] == ["室", "壁"]
        repeated = calendar_mansion("1969-09-30", zone="Pacific/Kwajalein")
        assert repeated["date_support"]["civil_support_seconds"] == 47 * 3600
        assert len(repeated["calendar_candidates"]) == 3
        r = calculate_sukuyo_compatibility(
            person1_date="2024-08-04",
            person2_date="2024-08-04",
            calendar_profile="hinoo_t1299_host27",
            person2_calendar_day_part="second_half",
        )
        assert r["status"] == "partial" and r["pair"] is None
        assert [
            (v["person1_su27"], v["pair"])
            for v in r["candidate_relation_analysis"]["rows"]
        ] == [("星", "栄親"), ("张", "命")]
        assert "candidate_relation_analysis" in required_quote_paths("compatibility")
        results = [
            calculate_suzhan_analysis(
                date="2024-08-04",
                time="09:00:00",
                zone="+08:00",
                calendar_profile="hinoo_t1299_host27",
                calendar_day_part=part,
            )
            for part in ("first_half", "second_half")
        ]
        assert [r["sukuyo"]["day_mansion"] for r in results] == ["星", "张"]
        capture = results[0]["sukuyo"]["calendar"]["profile_calculation"]
        assert (
            capture["source_bundle_sha256"]
            == capture["host_calculation"]["source_bundle_sha256"]
            == capture["short_month_assignment"]["omitted_day_calculation"][
                "source_bundle_sha256"
            ]
        )
        cached_primary = capture["hinoo_source"]["cached_primary_excerpt"]
        assert cached_primary["complete_original_source_bytes_sha256"] is None
        assert len(cached_primary["windows"]) == 2
        direct_primary = capture["hinoo_source"]["downloaded_primary_edition"]
        assert (
            capture["hinoo_source"]["active_primary_evidence"]
            == "downloaded_primary_edition"
        )
        assert (
            direct_primary["publisher_html_response_sha256"]
            == "74c63f5151c2b8c3ac554f7a0acae0776e5247e740a712834e1b600a065050e6"
        )
        assert len(direct_primary["calendar_apparatus"]) == 5
        assert direct_primary["downloaded_calendar_windows"][1]["text"].endswith("也｣")
        assert not direct_primary["facsimile_collation_complete"]
        critical = capture["hinoo_source"]["critical_calendar_reference"]
        readings = critical["selected_example_comparisons"]
        assert [row["kyoto_manuscript_mansion"] for row in readings] == [
            "虚",
            "星",
            "室",
        ]
        assert all(row["manuscript_matches_host"] for row in readings)
        assert readings[2]["taisho_literal_mansion"] == "星"
        assert not readings[2]["taisho_literal_matches_host"]
        assert critical["selected_primary"]["catalogue_copy_description"] == "新写"
        assert not critical["selected_primary"][
            "identified_as_taisho_base_or_ko_witness"
        ]
        assert not critical["complete_critical_edition_accepted"]
        natal_positions = calculate_suzhan_analysis(
            date="2025-03-04", time="12:00:00", zone="+08:00", natal_mansion="婁"
        )["sukuyo"]["six_palace_reference"]
        assert {r["name"]: r["mansion"] for r in natal_positions["members"]} == {
            "命": "娄",
            "事": "星",
            "意": "毕",
            "聚": "氐",
            "同": "箕",
            "克": "轸",
        }
        assert not natal_positions["seven_luminary_transits_evaluated"]
        assert not natal_positions["joint_reading_requirement"]["evaluated"]
        assert "sukuyo.six_palace_reference" in required_quote_paths("activity")
        assert results[0]["astronomy"] == results[1]["astronomy"]
        assert results[0]["astronomy"] is not None
        c = calendar_mansion(
            "1957-09-24",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
        assert c["status"] == "partial" and c["candidate_su27s"] == ["角", "轸"]
        precedence = c["profile_calculation"]["short_month_assignment"][
            "leap_short_month_precedence"
        ]
        assert not precedence["source_rule_priority_established"]
        assert [
            row["first_half_calculation"]["direct_mansion"]
            for row in precedence["reconstruction_calculations"]
        ] == ["角", "轸"]
        native_hinoo = day_evidence(c)["reading_text"]
        assert "前半按8月1日查得角" in native_hinoo
        assert "前半按7月30日查得轸" in native_hinoo
        assert "12月30日室；大正选文" in native_hinoo
        assert "12月30日星；本档案宿主望宿算法" in native_hinoo
        assert "未识别为大正底本或甲本" in native_hinoo
        assert "不将其认定为无条件删文" in native_hinoo
        report["native_hinoo_branch_and_manuscript_reading"] = "passed"
        activity_results = [
            calculate_suzhan_analysis(
                date="2025-03-04",
                time="12:00:00",
                zone="+08:00",
                activity="commerce",
                activity_details=details,
            )
            for details in ([], ["borrowing"])
        ]
        states = [
            next(
                v
                for v in r["sukuyo"]["activity_assessment"]["layers"]
                if v["layer"] == "lower_mansion"
            )["status"]
            for r in activity_results
        ]
        assert states == ["conditional_only", "caution"]
        assert activity_results[0]["astronomy"] == activity_results[1]["astronomy"]
        doctrine = activity_results[0]["sukuyo"]["conjunction_doctrine"]
        assert doctrine["selected_group"]["id"] == "before_arrival_six"
        assert not doctrine["applied_to_physical_moon"]
        conjunction_results = [
            calculate_suzhan_analysis(
                date="2025-03-13",
                time="12:00:00",
                zone="+08:00",
                activity="travel",
                activity_details=details,
            )
            for details in (
                ["journey_abroad"],
                ["journey_abroad", "long_distance_journey"],
            )
        ]
        for expected, result in zip((False, True), conjunction_results):
            matched = result["sukuyo"]["activity_assessment"]["matched_rules"]
            assert (
                "t1299_lower_mansion_18" in {r["rule_id"] for r in matched}
            ) is expected
        clock = conjunction_results[0]["sukuyo"]["calendar_day"]["clock_doctrine"]
        assert clock["day_parts"] == clock["night_parts"] == 8
        assert clock["intradaily_luminary_order"] is None
        comparative = clock["comparative_time_systems"]
        assert not comparative["applied_to_runtime_clock"]
        assert comparative["witnesses"][0]["daily_time_units"] == 30
        assert comparative["witnesses"][1]["lay_day_parts"] == 4
        historical = clock["historical_clock_arithmetic"]
        assert historical["selected_model"]["koku_per_day"] == 50
        assert historical["table_check"]["paired_readings_checked"] == 42
        assert historical["table_check"]["residual_counts_by_exact_fun"] == {
            "0": 34,
            "1": 4,
            "-1/2": 2,
            "-1": 2,
        }
        assert not historical["applied_to_runtime_day_boundary"]
        assert not historical["seasonal_axis"]["civil_date_conversion_established"]
        assert historical["exact_unit_relations"]["nominal_seconds_per_half_fun"] == {
            "numerator": 144,
            "denominator": 1,
        }
        report["selected_guchureki_clock_units_and_retained_residuals"] = "passed"
        for civil, correction in [
            ("2025-01-07", "正文水曜，校记重建火曜"),
            ("2025-02-26", "正文火曜，校记重建水曜"),
        ]:
            result = calculate_suzhan_analysis(
                date=civil, time="12:00:00", zone="+08:00"
            )
            assert correction in result["sukuyo"]["reading_text"]
        report["native_weekday_origin_and_comparative_time_units"] = "passed"
        directed = calculate_suzhan_analysis(
            date="2025-03-13",
            time="12:00:00",
            zone="+08:00",
            activity="travel",
            activity_details=["northbound_journey"],
        )["sukuyo"]
        north = next(
            r
            for r in directed["activity_assessment"]["matched_rules"]
            if r["rule_id"] == "t1299_direction_01"
        )
        assert (
            north["assessment"] == "caution" and north["auspicious_time_cannot_release"]
        )
        wall = calculate_suzhan_analysis(
            date="2025-01-30",
            time="12:00:00",
            zone="+08:00",
            activity="travel",
            activity_details=["southbound_journey"],
        )["sukuyo"]
        assert wall["activity_assessment"]["evidence_status"] == "conflicted"
        assert wall["directional_travel"]["physical_palace_computed"] is False
        from fatebridge.core.sukuyo_special_days import special_day_evidence

        well = special_day_evidence(
            "井", 2, weekday_basis="modern_utc_plus08_civil_midnight"
        )
        assert well["primary"]["matched_labels"] == []
        assert next(
            w for w in well["comparisons"] if w["witness"] == "upper_ming_apparatus"
        )["matched_labels"] == ["甘露"]
        stomach = special_day_evidence(
            "胃", 0, weekday_basis="modern_utc_plus08_civil_midnight"
        )
        lower = next(
            w for w in stomach["comparisons"] if w["witness"] == "lower_taisho"
        )
        assert (
            lower["matched_labels"] == []
            and not lower["labels_complete_for_selected_day"]
        )
        assert lower["unresolved_rows"][0]["literal_mansion"] == "冒"
        printed_tail = special_day_evidence(
            "尾", 6, weekday_basis="modern_utc_plus08_civil_midnight"
        )
        direct = printed_tail["direct_printed_comparisons"][0]
        assert direct["matched_labels"] == ["金刚峰"]
        assert printed_tail["primary"]["matched_labels"] == []
        assert not direct["applied_to_primary"]
        assert direct["source_reference"]["accepted_mansion_readings"] == 20
        printed_thursday = special_day_evidence(
            "亢", 4, weekday_basis="modern_utc_plus09_civil_midnight"
        )["direct_printed_comparisons"][0]
        assert not printed_thursday["labels_complete_for_selected_day"]
        assert printed_thursday["unresolved_rows"][0]["mansion"] is None
        assert printed_thursday["unresolved_rows"][0]["candidate_readings"] == [
            "巨",
            "亢",
        ]
        report["direct_printed_special_variants_and_unaccepted_glyph"] = "passed"
        for basis, civil, offset in [
            ("chinese_hko_utc08", "2000-01-01", "08"),
            ("japanese_hutime_1002_1_utc09", "2000-01-01", "09"),
            ("japanese_naoj_historical_utc09", "0820-03-22", "09"),
        ]:
            bounded = day_evidence(
                calendar_mansion(civil, "00:30:00", "+09:00", calendar_basis=basis)
            )
            assert bounded["special_day_evidence"]["weekday_basis"] == (
                f"modern_utc_plus{offset}_civil_midnight"
            )
            assert f"现代UTC+{offset}历日" in bounded["special_day_evidence"]["scope"]
            assert (
                bounded["special_day_evidence"]["weekday_basis"]
                == bounded["weekday"]["basis"]
            )
            assert not bounded["special_day_evidence"][
                "classical_daybreak_boundary_acceptance"
            ]
            input_calendar = bounded["calendar"]
            native = bounded["reading_text"]
            assert input_calendar["input_datetime"] in native
            assert f"输入时区{input_calendar['input_timezone']}" in native
            assert f"所选宿主时区{input_calendar['calendar_timezone']}" in native
            assert f"参考历日为{input_calendar['calendar_date']}" in native
            assert "将同一时刻换算" in native
            assert "已知民用钟时不表示已确定古代平明日界" in native
        report["special_day_selected_host_weekday_boundary"] = "passed_three_bases"
        report["native_input_instant_and_host_reference_date"] = "passed_three_bases"
        learning = calculate_suzhan_analysis(
            date="2025-04-15",
            time="12:00:00",
            zone="+08:00",
            activity="study",
            activity_details=["religious_learning"],
        )["sukuyo"]
        assert {
            "t1299_special_upper_ganlu_learning_v1",
            "t1299_special_lower_ganlu_learning_v1",
        } <= {r["rule_id"] for r in learning["activity_assessment"]["matched_rules"]}
        opposed = calculate_suzhan_analysis(
            date="2025-03-04",
            time="12:00:00",
            zone="+08:00",
            activity="commerce",
            activity_details=["collecting_debt"],
        )["sukuyo"]
        matched_ids = {
            r["rule_id"] for r in opposed["activity_assessment"]["matched_rules"]
        }
        assert {"t1299_activity_29", "t1299_lower_method_weekday_08"} <= matched_ids
        assert opposed["activity_assessment"]["evidence_status"] == "conflicted"
        assert opposed["lower_methods"]["weekday"]["luminary"] == "火"
        generic_personal = calculate_suzhan_analysis(
            date="2025-03-04",
            time="12:00:00",
            zone="+08:00",
            natal_mansion="奎",
            activity="travel",
        )["sukuyo"]
        assert not [
            r
            for r in generic_personal["activity_assessment"]["matched_rules"]
            if r["layer"] == "sanjiu"
        ]
        residence_entry = calculate_suzhan_analysis(
            date="2025-03-04",
            time="12:00:00",
            zone="+08:00",
            natal_mansion="娄",
            activity="travel",
            activity_details=["long_distance_traveler_entering_residence"],
        )["sukuyo"]
        assert {
            r["rule_id"]
            for r in residence_entry["activity_assessment"]["matched_rules"]
            if r["layer"] == "sanjiu"
        } == {"t1299_sanjiu_lower_16"}
        assert not residence_entry["personal_day"]["source_day_evidence"][
            "priority_clause_applied_to_aggregate"
        ]
        inherited = calculate_suzhan_analysis(
            date="2025-03-04",
            time="12:00:00",
            zone="+08:00",
            activity="commerce",
            activity_details=["purchase_precious_goods"],
        )["sukuyo"]["activity_assessment"]
        assert inherited["effective_activity_details"] == [
            "purchase_precious_goods",
            "purchase",
        ]
        clothes = calculate_suzhan_analysis(
            date="2025-02-11",
            time="12:00:00",
            zone="+08:00",
            activity="clothing",
            activity_details=["tailoring_garments"],
        )
        assert (
            clothes["sukuyo"]["activity_assessment"]["evidence_status"] == "conflicted"
        )
        assert (
            clothes["sukuyo"]["clothing_reference"]["primary_assessment"] == "caution"
        )
        assert clothes["sukuyo"]["candidate_days"] == []
        from fatebridge.core.sukuyo_clothing import clothing_reference

        ming = clothing_reference({"natal_su27": "井"})["candidate_references"][0][
            "comparisons"
        ][1]
        assert ming["assessment"] is None and not ming["applied_to_primary"]
        assert "sukuyo.candidate_days" in required_quote_paths("activity")
        assert "sukuyo.clothing_reference" in required_quote_paths("clothing")
        from fatebridge.core.sukuyo_weekday import (
            civil_weekday,
            classical_calibration_precision,
            classical_mean_cycle_arithmetic,
            classical_solar_recalculation,
            classical_source_year_count,
            classical_weekday_arithmetic,
        )

        manuscript = classical_weekday_arithmetic(2, 9, 1)
        assert manuscript["trace"]["accumulated_days"] == 1005
        assert manuscript["luminary"] == "木"
        assert not manuscript["applied_to_primary_calendar"]
        assert civil_weekday("0840-02-11", "UTC+09:00")["luminary"] == "土"
        assert (
            classical_mean_cycle_arithmetic(137)["omission_days"]["rounded_decimal_12"]
            == "15112.873399715505"
        )
        assert (
            classical_solar_recalculation(2603)["recalibrated_accumulated_days"][
                "truncated_decimal_12"
            ]
            == "950731.022333144959"
        )
        assert classical_source_year_count(1816)["elapsed_years"] == 2603
        precision = classical_calibration_precision()
        assert precision["selected_precision_discrepancies"] == [
            "base_omission_plus_printed_correction",
            "nominal_days_minus_printed_omissions",
        ]
        assert not precision["complete_lunar_secular_derivation_accepted"]
        invalid_context = calendar_mansion("2025-03-04", "12:00:00", "+08:00")
        del invalid_context["calendar_timezone"]
        from fatebridge.core.sukuyo import day_evidence

        try:
            day_evidence(invalid_context)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing host boundary was silently treated as UTC08")
        report["selected_manuscript_integer_arithmetic_without_civil_mapping"] = (
            "passed"
        )
        report["selected_fractional_products_and_missing_boundary_rejection"] = "passed"
        report["selected_printed_year_rule_and_retained_precision_discrepancies"] = (
            "passed_with_two_retained_source_precision_discrepancies"
        )
        assert reference_cell("翼", 1)["palace_name"] == "师子宫"
        assert reference_cell("翼", 2)["palace_name"] == "女宫"
        assert palace_reference({"natal_su27": "翼"})["selected_palace"] is None
        queried = calculate_sukuyo_compatibility(
            person1_date="1990-06-15",
            person2_date="1992-03-20",
            person1_textual_pada=1,
            person2_textual_pada=4,
        )
        ref = queried["person1"]["palace_reference"]
        assert ref["textual_pada"] == 1 and not ref["birth_pada_established"]
        for spec in CATALOG:
            if spec.key in ("suzhan", "sukuyo_compatibility"):
                assert "calendar_profile" in spec.request_model.model_fields
                schema = spec.output_model.model_json_schema()
                if spec.key == "sukuyo_compatibility":
                    assert "SukuyoCandidateAnalysis" in schema["$defs"]
        paths = [
            "core/sukuyo_weekday.py",
            "data/sukuyo_t30107_weekday_arithmetic.json",
            "data/sukuyo_t30107_recalculation.json",
            "data/sukuyo_wakita_weekday.json",
            "data/sukuyo_t30107_calibration.json",
            "core/sukuyo_clothing.py",
            "data/sukuyo_t1299_clothing.json",
            "core/sukuyo_taibai.py",
            "data/sukuyo_t1299_taibai.json",
            "core/sukuyo_historical_calendar.py",
            "data/sukuyo_japanese_historical_v1.json",
            "validation/sukuyo_historical_sources.py",
            "core/sukuyo.py",
            "core/sukuyo_calendar_basis.py",
            "core/sukuyo_japanese_calendar.py",
            "core/sukuyo_date_support.py",
            "core/sukuyo_profiles.py",
            "core/sukuyo_hinoo_critical.py",
            "data/sukuyo_t2465_critical.json",
            "core/sukuyo_lower.py",
            "core/sukuyo_lower_methods.py",
            "core/sukuyo_padas.py",
            "core/sukuyo_sources.py",
            "core/sukuyo_activities.py",
            "core/sukuyo_calendar_text.py",
            "core/sukuyo_directions.py",
            "core/sukuyo_documentary.py",
            "core/sukuyo_guchureki_clock.py",
            "data/sukuyo_selected_text_layers.json",
            "data/sukuyo_japanese_selected_calendar.json",
            "core/sukuyo_special_days.py",
            "core/sukuyo_printed_special.py",
            "data/sukuyo_wakita_special_days.json",
            "data/sukuyo_comparative_time_units.json",
            "data/sukuyo_t1299_clock_transposition.json",
            "data/sukuyo_naoj_guchureki_clock.json",
            "core/sukuyo_sanjiu_days.py",
            "core/sukuyo_six_palaces.py",
            "core/suzhan_astronomy.py",
            "core/guolao.py",
            "core/fixed_star_paths.py",
            "core/astro/birth.py",
            "core/astro/time_scales.py",
            "core/ephemeris_runtime.py",
            "core/output_reference.py",
            "core/local_techniques/suzhan.py",
            "validation/sukuyo.py",
            "validation/sukuyo_study.py",
            "validation/sukuyo_calendar_sources.py",
            "services/divination.py",
            "data/sukuyo_t1299_calendar_profiles.json",
            "data/sukuyo_japanese_daily_v1.json",
            "data/sukuyo_t1299_days.json",
            "data/sukuyo_t1299_travel_directions.json",
            "data/sukuyo_t1299_special_days.json",
            "data/sukuyo_t1299_sanjiu_days.json",
            "data/sukuyo_t1299_six_palaces.json",
            "data/sukuyo_t1299_activities.json",
            "data/sukuyo_t1299_lower_mansions.json",
            "data/sukuyo_t1299_lower_methods.json",
            "data/sukuyo_t1299_palace_padas.json",
            "data/guolao/sefstars.txt",
            "data/guolao/sources.json",
        ]
        if args.source_root:
            for rel in paths:
                assert (stage / "fatebridge" / rel).read_bytes() == (
                    args.source_root / "src/fatebridge" / rel
                ).read_bytes(), rel
            for rel, name in [
                ("core/requests/divination.py", "SuZhanRequest"),
                ("core/requests/compatibility.py", "SukuyoCompatibilityRequest"),
            ]:

                def node(path):
                    return next(
                        n
                        for n in ast.parse(path.read_text()).body
                        if isinstance(n, ast.ClassDef) and n.name == name
                    )

                assert ast.dump(node(stage / "fatebridge" / rel)) == ast.dump(
                    node(args.source_root / "src/fatebridge" / rel)
                ), name
            # Check the artifact's actual sky pipeline against frozen external
            # observations, not only against source files or internal invariance.
            from fatebridge.core import ephemeris_runtime
            from fatebridge.core.astro.birth import build_astro_birth_info
            from fatebridge.core.suzhan_astronomy import build_equatorial_mansions

            reference_path = (
                args.source_root / "tests/fixtures/sukuyo-equatorial-horizons.json"
            )
            reference_raw = reference_path.read_bytes()
            reference = json.loads(reference_raw)
            assert reference["tolerance_arcseconds"] == 2.0
            skies = {}
            sky_errors = []
            with (
                patch.object(
                    ephemeris_runtime, "_configured_path", str(stage / "no-se1")
                ),
                patch.dict("os.environ", {"SE_EPHE_PATH": ""}),
            ):
                for ref in reference["references"]:
                    assert (
                        hashlib.sha256(ref["response"]["result"].encode()).hexdigest()
                        == ref["response_sha256"]
                    )
                    for row in ref["rows"]:
                        when = datetime.fromisoformat(row["utc"])
                        if row["utc"] not in skies:
                            skies[row["utc"]] = build_equatorial_mansions(
                                build_astro_birth_info(
                                    birth_year=when.year,
                                    birth_month=when.month,
                                    birth_day=when.day,
                                    birth_hour=when.hour,
                                    birth_minute=when.minute,
                                    birth_second=when.second,
                                    birth_timezone="UTC",
                                    birth_latitude=0,
                                    birth_longitude=0,
                                )
                            )
                        actual = next(
                            b
                            for b in skies[row["utc"]]["bodies"]
                            if b["id"] == ref["body"]
                        )
                        ra_error = (
                            abs(
                                (
                                    actual["right_ascension"]
                                    - row["right_ascension"]
                                    + 180
                                )
                                % 360
                                - 180
                            )
                            * 3600
                        )
                        dec_error = (
                            abs(actual["declination"] - row["declination"]) * 3600
                        )
                        sky_errors.append(max(ra_error, dec_error))
            assert len(sky_errors) == 42
            assert max(sky_errors) <= reference["tolerance_arcseconds"]
            assert (
                reference_path.read_bytes() == reference_raw
            ), "JPL fixture changed during artifact validation"
            report["packaged_jpl_coordinates"] = {
                "reference_fixture_sha256": hashlib.sha256(reference_raw).hexdigest(),
                "positions_checked": len(sky_errors),
                "fixed_tolerance_arcseconds": reference["tolerance_arcseconds"],
                "maximum_error_arcseconds": max(sky_errors),
                "scope": "Artifact Moshier path against frozen JPL positions; not ancient mansion-boundary acceptance or all-epoch accuracy.",
            }
            from fatebridge.validation.sukuyo_calendar_sources import audit_candidate

            candidate = audit_candidate(
                args.source_root / "tests/fixtures/sukuyo_hutime_v1"
            )
            assert not candidate["structural_import_eligible"]
            assert not candidate["runtime_calendar_enabled"]
            assert {f["kind"] for f in candidate["blocking_findings"]} == {
                "missing_advertised_range_queries",
                "month_interval_conflicts",
                "published_calendar_id_probe_nulls",
                "day_month_period_disagreements",
            }
            report["japanese_candidate_source_admission"] = {
                "status": "rejected_with_preserved_findings",
                "blocking_findings": candidate["blocking_findings"],
                "source_archive_sha256": candidate["source_archive_sha256"],
                "runtime_calendar_enabled": False,
            }
        report.update(
            {
                "isolated_package_import": True,
                "taibai_day_table_missing_ming_rows_and_nonphysical_scope": "passed",
                "historical_reference_disagreements_reform_and_early_date_support": "passed",
                "default_fullmoon": "passed",
                "detached_source_payload_and_one_profile_capture": "passed",
                "personal_day_distance_departure_and_residence_entry_scopes": "passed",
                "long_operator_and_catalogue_native_paths": "passed",
                "literal_catalogue_search_separator": "passed",
                "actor_purpose_and_social_action_scope": "passed",
                "japanese_daily_reference_boundaries_and_sky_invariance": "passed",
                "natal_six_palace_positions_without_transit_assertion": "passed",
                "direct_t2465_primary_metadata_and_apparatus": "passed",
                "source_inline_gloss_without_first_night_rule": "passed",
                "complete_foreign_date_support_without_birth_time": "passed",
                "hinoo_halves_and_candidates": "passed",
                "hinoo_direct_manuscript_controls_and_unselected_priority": "passed",
                "physical_sky_invariant": "passed",
                "partial_leap_precedence": "passed",
                "catalog_and_nested_schema": "passed",
                "lower_clause_detail_matching": "passed",
                "conjunction_not_applied_to_physical_moon": "passed",
                "palace_pada_reference_without_birth_inference": "passed",
                "conjunctive_source_scope_and_uninvented_clock": "passed",
                "opposing_lower_weekday_witnesses_and_detail_inheritance": "passed",
                "explicit_travel_directions_and_opposite_wall_clauses": "passed",
                "special_day_witnesses_unresolved_literals_and_religious_scope": "passed",
                "compared_whole_files": paths if args.source_root else [],
                "compared_request_class_ast": (
                    ["SuZhanRequest", "SukuyoCompatibilityRequest"]
                    if args.source_root
                    else []
                ),
                "scope": "Extracted FateBridge artifact with existing uv dependencies; not a clean installation or whole-workspace byte comparison.",
            }
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
