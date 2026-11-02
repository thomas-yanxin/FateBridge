"""A modern transcription of a related old preface, not a calendar override."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_koya_preface_aitani2013.json"
)
LUMINARIES = ("月", "火", "水", "木", "金", "土", "日")


def preface_reference(arc: dict[str, Any]) -> dict[str, Any]:
    """Bind the companion to the actually loaded ARC preface, not its filename."""
    loaded = load_source(SOURCE)
    bundle = loaded.data
    identity = bundle["arc_companion_identity"]
    images = {
        str(i["frame"]): i["image_sha256"]
        for i in arc["preface_selected_reference"]["images"]
    }
    if (
        arc["record"] != identity["record"]
        or images != identity["preface_images_sha256"]
        or arc["preface_selected_reference"]["visible_signature"]
        != identity["signature"]
    ):
        raise ValueError("序跋翻刻对照与本次ARC序文身份不符，须重新校核")
    return {**bundle, "source_bundle_sha256": loaded.sha256}


def dated_weekday_reference(
    civil: date, lunar: tuple[int, int, int, bool], calendar_reference: dict[str, Any]
) -> dict[str, Any] | None:
    """Compare a same-label NAOJ date, retaining the source's actual wording.

    Neighbouring days are a diagnostic control, not inferred birth-time/date
    candidates. A conjectured Tang day label never becomes a Japanese day.
    """
    loaded = load_source(SOURCE)
    records = loaded.data["dated_records"]
    selected = next(
        (
            r
            for r in records
            if (*[r[k] for k in ("lunar_year", "lunar_month", "lunar_day")], False)
            == lunar
        ),
        None,
    )
    if selected is None:
        return None
    actual = LUMINARIES[civil.weekday()]
    neighbours = [
        {
            "civil_day_offset": offset,
            "civil_date": (civil + timedelta(days=offset)).isoformat(),
            "luminary": LUMINARIES[(civil + timedelta(days=offset)).weekday()],
        }
        for offset in (-1, 0, 1)
    ]
    printed_ganzhi = selected["printed_day_ganzhi"]
    return {
        "ruleset_id": loaded.data["id"],
        "source_bundle_sha256": loaded.sha256,
        "source_url": loaded.data["source_url"],
        "pdf_sha256": loaded.data["pdf_sha256"],
        "printed_page": 78,
        "source_record": deepcopy(selected),
        "comparison_basis": "same_lunar_label_under_declared_NAOJ_reference_not_verified_Tang_conversion",
        "reference_civil_date": civil.isoformat(),
        "reference_calendar_source_sha256": calendar_reference["source_bundle_sha256"],
        "reference_lunar_fields": list(lunar),
        "reference_luminary": actual,
        "printed_luminary": selected["claimed_luminary"],
        "weekday_matches_under_same_label": actual == selected["claimed_luminary"],
        "reference_day_ganzhi": calendar_reference["day_ganzhi_reference"]["name"],
        "printed_day_ganzhi": printed_ganzhi,
        "ganzhi_matches_under_same_label": (
            printed_ganzhi == calendar_reference["day_ganzhi_reference"]["name"]
            if printed_ganzhi is not None
            else None
        ),
        "adjacent_civil_day_control": neighbours,
        "claimed_weekday_in_adjacent_day_control": any(
            r["luminary"] == selected["claimed_luminary"] for r in neighbours
        ),
        "neighbours_are_birth_date_candidates": False,
        "source_date_corrected": False,
        "source_error_established": False,
        "tang_calendar_conversion_evaluated": False,
        "historical_daybreak_accepted": False,
        "applied_to_primary_or_activities": False,
        "scope": "同名日本参考月日的条件性对照；源文历法身份及实物传承尚未核实。相合不认证古钟时，分歧不直接判抄误；邻日只检验固定标签前后一天，未据此选日、换历或改宿。",
    }


def preface_reading_lines(reference: dict[str, Any]) -> list[str]:
    p = reference["preface_selected"]
    lines = [
        f"另据會谷佳光2013年《和刻本佛典邦人序跋集成》成田山册，条目{reference['entry_number']}、书页77—78（PDF第83—84页）；"
        "所据成田山刊本题录为高野山經師八左衛門刊，非已认证与ARC同一实物。",
        f"该翻刻古序可读：{p['literal']}。这是序者的大小月说法与异本批评；"
        "不将其中重直兩日改解成桧尾前后半，也未据此确立闰月与小月的先后。虛／虚字形及馆藏号读录有异，未据此定ARC原字或藏本身份；原ARC草体初读及两处印表疑字继续保留。",
        "同条補入記另录806年正月二日丁卯密日、807年正月三日壬辰蜜日和808年二月七日蜜日；"
        "807年唐历正月四日仅为原文准拟，应当之说未验证。唐元和元年十二月小尽与夹注本国大月分层保留；"
        "記日、两古本说明和我大师录之推断分别保留，未把它们归给2013年编者或认证为当时原笔。",
        f"翻刻PDF指纹{reference['pdf_sha256']}，来源{reference['source_url']}；"
        "这些记日不确定平明钟时、逐时曜序、半日映射或现实效力。",
    ]
    lines.append(
        "2013翻刻按语中彼与曜之间一字仍未定，保留算／筭／等候选，不因别本或历算补定；"
        "馆藏号保留四六―一三四（イ）／四六―一二三四（イ）两读，接受值为空。"
    )
    if reference.get("arc_supplement_selected_reference"):
        arc = reference["arc_supplement_selected_reference"]
        lines.append(
            f"另已在ARC下卷{arc['record']}数字帧28、卷叶二十七定位同组记日；"
            f"正文二月七日蜜日照留，上栏校按另称{arc['marginal_selected_literal']}。"
            "这是该图的正文与校按两层，不倒改2013翻刻，也未认证两件馆藏实物相同。"
            "校按提出的正月七日须另作条件比较，不能改成已确认的出生日期或删除正文不合。"
        )
        lines.append(
            "该ARC校按小字中，"
            f"{arc['uncertain_marginal_spans'][0]['location']}词读未定；"
            "己丑后密／蜜、末尾且／自及相字仍有未定读录；"
            "上面的省略号选段不是完整定本。案语彼后筭字也保留一方暂读、一方读定的差别，"
            "不倒改2013翻刻的未定字，不以相合的历算补字；校按作者及形成时间未认证。"
        )
    return lines


def editorial_weekday_reference(
    civil: date, lunar: tuple[int, int, int, bool], calendar_reference: dict[str, Any]
) -> dict[str, Any] | None:
    """Keep an actual marginal correction as evidence, never as input repair."""
    loaded = load_source(SOURCE)
    arc = loaded.data.get("arc_supplement_selected_reference")
    if arc is None:
        return None
    selected = next(
        (r for r in arc["dated_claims"] if tuple(r["lunar_fields"]) == lunar), None
    )
    if selected is None:
        return None
    actual = LUMINARIES[civil.weekday()]
    ganzhi = calendar_reference["day_ganzhi_reference"]["name"]
    return {
        "source_bundle_sha256": loaded.sha256,
        "source_record": arc["record"],
        "source_image_sha256": arc["image_sha256"],
        "source_url": arc["permalink"],
        "source_layer": "printed_upper_margin_annotation_not_main_date_record",
        "marginal_literal": arc["marginal_selected_literal"],
        "selected_claim": deepcopy(selected),
        "comparison_basis": "same_lunar_label_under_declared_NAOJ_reference",
        "reference_calendar_source_sha256": calendar_reference["source_bundle_sha256"],
        "reference_civil_date": civil.isoformat(),
        "reference_luminary": actual,
        "reference_day_ganzhi": ganzhi,
        "weekday_matches_under_same_label": actual == selected["claimed_luminary"],
        "ganzhi_matches_under_same_label": ganzhi == selected["printed_day_ganzhi"],
        "main_text_month_two_record_retained": True,
        "ganzhi_from_margin_inserted_into_main_text": False,
        "main_text_error_or_corrected_date_certified": False,
        "birth_date_or_primary_changed": False,
        "historical_daybreak_accepted": False,
        "independent_observation_added": False,
        "scope": "只比较该图校按提出的具名历日；正文原月、校按拟正月、现代参考分别保留，未将校按当原笔或把相合当古钟时认证。",
    }


def editorial_weekday_reading_lines(reference: dict[str, Any]) -> list[str]:
    row = reference["selected_claim"]
    weekday = "相合" if reference["weekday_matches_under_same_label"] else "不合"
    ganzhi = "相合" if reference["ganzhi_matches_under_same_label"] else "不合"
    return [
        f"ARC下卷帧28上栏校按另录{reference['marginal_literal']}；本次对应的是{row['claim_role']}，"
        f"同名日本参考为{reference['reference_civil_date']}、{reference['reference_day_ganzhi']}、"
        f"{reference['reference_luminary']}曜，与校按曜项{weekday}、干支{ganzhi}。"
        "正文二月七日蜜日及其参考不合仍保留，己丑／己未只在校按层，未补进原正文。"
        "未按校按更换本次输入、主宿或候选，也未认证正月为唯一史实、校按作者或古代日界。"
    ]


def dated_weekday_reading_lines(reference: dict[str, Any]) -> list[str]:
    row = reference["source_record"]
    result = (
        "相合" if reference["weekday_matches_under_same_label"] else "不同，保留分歧"
    )
    lines = [
        f"補入記原录{row['literal']}；只以同名月日查NAOJ日本参考，得{reference['reference_civil_date']}、"
        f"{reference['reference_day_ganzhi']}、{reference['reference_luminary']}曜，与原录{row['weekday_literal']}"
        f"按T1299密／蜜词项对照的日曜{result}。不是已经核定的唐历换算。"
    ]
    if row.get("tang_alternative"):
        lines.append(
            f"该条另称{row['tang_alternative']['literal']}；保留准拟及应当语气，"
            "未用日本同名正月四日替代唐历四日，未重建唐历或认证两历对应。"
        )
    if reference["printed_day_ganzhi"] is None:
        lines.append("此条未录日干支，未把参考干支补成原文。")
    elif reference["ganzhi_matches_under_same_label"]:
        lines.append("所录干支与本次参考相合；这仍不校准日内平明钟界。")
    else:
        lines.append("所录干支与本次参考不同，原字保留，未改写成参考干支。")
    if reference["weekday_matches_under_same_label"]:
        neighbours = "、".join(
            f"{r['civil_date']}{r['luminary']}曜"
            for r in reference["adjacent_civil_day_control"]
        )
        lines.append(
            f"固定同名参考日的邻日诊断为{neighbours}；不是出生候选或唐历换算，未据此改日或校准平明。"
        )
    if not reference["weekday_matches_under_same_label"]:
        labels = "、".join(
            f"{r['civil_day_offset']:+d}日{r['luminary']}曜"
            for r in reference["adjacent_civil_day_control"]
        )
        inclusion = (
            "包含" if reference["claimed_weekday_in_adjacent_day_control"] else "不包含"
        )
        lines.append(
            f"固定同名参考日的邻日诊断为{labels}，{inclusion}原录日曜；"
            "这三个标签不是新增出生候选，不能靠选邻日、换月份或改原字消除分歧。"
            "原记录的历法身份、传写与未定日界分别待核，不直接认定抄误。"
        )
    return lines
