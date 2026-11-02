"""Exact arithmetic of the selected printed clock, without a physical epoch."""

import json
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.utils.errors import NumerologySourceError

RULESET_ID = "heluo_wenming_baike_clock_v1"
SOURCE_PATH = Path(__file__).resolve().parents[1] / "data/heluo/clock-v1.json"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
LONG_BRANCHES = ("寅", "申", "巳", "亥")
PDF_SHA256 = "fd203ebcd4dc355dbb1ddd3cbee0a72051a2ca6f7a3e0945027690aac8de0b0c"


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        expected = dict(
            day_ke=100,
            twelve_base_total_ke=96,
            extra_branch_ke=9,
            nominal_year_days=360,
            printed_year_days=365,
            extra_month_shi=5,
            months=12,
            extra_year_shi=60,
            daily_extra_ke=1,
            daily_extra_fen=7,
            block_nominal_days=6,
            block_extra_shi=1,
        )
        if (
            data["ruleset_id"] != RULESET_ID
            or data["version"] != "1.0.0"
            or data["source_pdf_sha256"] != PDF_SHA256
            or data["source_pdf_pages"] != [41]
            or data["extra_branches_in_printed_order"] != list(LONG_BRANCHES)
            or data["source_fen_per_ke"] is not None
            or any(
                type(data[k]) is not int or data[k] != n for k, n in expected.items()
            )
        ):
            raise ValueError("所选百刻原句或未定分制被改写。")
        for key in ("source_title", "source_url", "review_status", "scope"):
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError("百刻来源元数据缺失。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_clock_source") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def _ratio(value: Fraction) -> dict[str, int]:
    return dict(numerator=value.numerator, denominator=value.denominator)


def source_branch_partition(*, origin_branch: str) -> list[dict[str, Any]]:
    """Rotate the printed count cycle from an explicitly supplied branch origin.

    An origin is an algebraic branch, not midnight or a converted civil instant.
    """
    source = _source()
    if (
        not isinstance(origin_branch, str)
        or len(origin_branch) != 1
        or origin_branch not in BRANCHES
    ):
        raise ValueError("须明确指定有效时支原点；不默认子初或子正。")
    start = BRANCHES.index(origin_branch)
    rows = []
    cursor = 0
    for i in range(12):
        branch = BRANCHES[(start + i) % 12]
        length = (
            source["extra_branch_ke"]
            if branch in LONG_BRANCHES
            else source["twelve_base_total_ke"] // 12
        )
        rows.append(
            dict(
                branch=branch, start_ke=cursor, end_ke=cursor + length, length_ke=length
            )
        )
        cursor += length
    if cursor != source["day_ke"]:
        raise NumerologySourceError("invalid_heluo_clock_source")
    return rows


def source_branch_at_ke(value: int | Fraction, *, origin_branch: str) -> dict[str, Any]:
    """Locate an exact count in a single source cycle; do not wrap at100."""
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError("源刻须为整数或精确Fraction，不能用布尔或浮点近似。")
    value = Fraction(value)
    source = _source()
    if not 0 <= value < source["day_ke"]:
        raise ValueError("单周期源刻须在[0,100)；下一周期不能静默折回。")
    row = next(
        r
        for r in source_branch_partition(origin_branch=origin_branch)
        if r["start_ke"] <= value < r["end_ke"]
    )
    return dict(
        **row,
        origin_branch=origin_branch,
        source_ke=_ratio(value),
        ke_into_branch=_ratio(value - row["start_ke"]),
        physical_epoch_established=False,
    )


def compare_daily_extra(*, fen_per_ke: int) -> dict[str, Any]:
    """Conditional equal-shi comparison, not verification of a historical scale."""
    if type(fen_per_ke) is not int or fen_per_ke <= 0:
        raise ValueError("比较用的每刻分数须明确给出正整数，不设默认分制。")
    source = _source()
    extra = Fraction(source["daily_extra_ke"]) + Fraction(
        source["daily_extra_fen"], fen_per_ke
    )
    year = Fraction(source["nominal_year_days"]) * (1 + extra / source["day_ke"])
    difference = year - source["printed_year_days"]
    return dict(
        assumed_fen_per_ke=fen_per_ke,
        extra_ke_per_day=_ratio(extra),
        year_days=_ratio(year),
        difference_from_printed_year_days=_ratio(difference),
        arithmetic_closes=difference == 0,
        source_fen_scale_verified=False,
        physical_clock_applied=False,
        assumption="100ke/day; uniform extra allocation; 12 equal shi/day. This projection does not establish the printed unequal branch clock as a physical clock.",
    )


def source_six_day_blocks(*, origin_branch: str, blocks: int) -> list[dict[str, Any]]:
    """Six nominal source days plus one branch shift, at branch starts only.

    These are relative source-ke boundaries. No daily interpolation, inner-ke
    transfer rule, civil timestamp or actual solar-month boundary is supplied.
    """
    if type(blocks) is not int or not 1 <= blocks <= 60:
        raise ValueError("须明确给出一至六十块；此处只推一个原式大数年。")
    source = _source()
    partition = source_branch_partition(origin_branch=origin_branch)
    result = []
    cursor = 0
    nominal_ke = source["block_nominal_days"] * source["day_ke"]
    for i in range(blocks):
        current = partition[i % 12]
        following = partition[(i + 1) % 12]
        end = cursor + nominal_ke + current["length_ke"]
        result.append(
            dict(
                block_index=i + 1,
                branch=current["branch"],
                next_branch=following["branch"],
                start_ke=cursor,
                end_ke=end,
                extra_ke=current["length_ke"],
                nominal_days=source["block_nominal_days"],
                origin_branch=origin_branch,
                branch_start_only=True,
                physical_epoch_established=False,
            )
        )
        cursor = end
    return result


def source_clock_evidence() -> dict[str, Any]:
    source = _source()
    ordinary = source["twelve_base_total_ke"] // 12
    expected_extra = Fraction(
        (source["printed_year_days"] - source["nominal_year_days"]) * source["day_ke"],
        source["nominal_year_days"],
    )
    required = Fraction(
        source["daily_extra_fen"], expected_extra - source["daily_extra_ke"]
    )
    return {
        **{
            k: source[k]
            for k in (
                "ruleset_id",
                "version",
                "source_title",
                "source_url",
                "source_pdf_sha256",
                "review_status",
                "scope",
            )
        },
        "source_pdf_pages": source["source_pdf_pages"][:],
        "loaded_sha256": source["loaded_sha256"],
        "day_ke": source["day_ke"],
        "base_ke": source["twelve_base_total_ke"],
        "extra_ke": source["day_ke"] - source["twelve_base_total_ke"],
        "branch_lengths": [
            dict(
                branch=b,
                length_ke=source["extra_branch_ke"] if b in LONG_BRANCHES else ordinary,
            )
            for b in BRANCHES
        ],
        "extra_branches_in_printed_order": list(LONG_BRANCHES),
        "physical_origin_branch": None,
        "daily_extra_literal": dict(
            ke=source["daily_extra_ke"], fen=source["daily_extra_fen"], fen_per_ke=None
        ),
        "annual_extra_literal": dict(
            nominal_days=source["nominal_year_days"],
            printed_days=source["printed_year_days"],
            monthly_extra_shi=source["extra_month_shi"],
            months=source["months"],
            annual_extra_shi=source["extra_year_shi"],
        ),
        "branch_shift_projection": dict(
            year_blocks=source["nominal_year_days"] // source["block_nominal_days"],
            extra_shi=source["extra_year_shi"],
            extra_ke=(source["extra_year_shi"] // 12) * source["day_ke"],
            total_source_days=_ratio(
                Fraction(source["nominal_year_days"])
                + Fraction(source["extra_year_shi"], 12)
            ),
            origin_basis="full_cycles_total_invariant; no_physical_origin_selected",
            branch_start_only=True,
            derived_only=True,
            source_fen_scale_selected=False,
            daily_internal_distribution_resolved=False,
        ),
        "equal_shi_projection": dict(
            extra_ke_per_nominal_day=_ratio(expected_extra),
            fen_per_ke_required_for_numeric_closure=_ratio(required),
            derived_only=True,
            source_fen_scale_verified=False,
        ),
        "physical_clock_applied": False,
        "calendar_mapping_complete": False,
        "constraints": [
            "寅申巳亥各九刻，其余各八刻，合一百刻；子丑等仅列循环支序，不据此指定午夜原点。",
            "六日进一时支只在明确支初原点下推相对源刻；六十块合五个额外百刻周期、总365源日，不因此解决日内添分或实际节月交接。",
            "所录段落每日添一刻七分，但未定义每刻分数；等长十二时辰假设下推得十八分一刻仅为数式相合条件，不是原典分制认证。",
            "该钟制及寄时未用于本次民用／真太阳钟或实际日卦日期；卦序仍按明确年标签、月序和日定式序计算。",
        ],
    }


def attach_clock_evidence(
    evidence: dict[str, Any], profile: dict[str, Any], context: dict[str, Any]
) -> None:
    evidence["rulesets"].append(
        {
            k: profile[k]
            for k in (
                "ruleset_id",
                "version",
                "source_title",
                "source_url",
                "source_pdf_sha256",
            )
        }
    )
    evidence["rulesets"][-1]["source_status"] = profile["review_status"]
    evidence["rule_trace"].append(
        dict(
            rule_id=RULESET_ID,
            source_section="卷一定時刻法；源钟式未转为本次实际日期",
            facts=dict(clock_profile=deepcopy(profile), year_context=deepcopy(context)),
        )
    )
    evidence["interpretation_constraints"].extend(profile["constraints"])


def source_clock_snapshot(profile: dict[str, Any]) -> str:
    branches = "".join(profile["extra_branches_in_printed_order"])
    lengths = {row["branch"]: row["length_ke"] for row in profile["branch_lengths"]}
    long_ke = lengths[profile["extra_branches_in_printed_order"][0]]
    ordinary = profile["base_ke"] // 12
    literal = profile["daily_extra_literal"]
    required = profile["equal_shi_projection"][
        "fen_per_ke_required_for_numeric_closure"
    ]
    ratio = (
        str(required["numerator"])
        if required["denominator"] == 1
        else f"{required['numerator']}/{required['denominator']}"
    )
    shift = profile["branch_shift_projection"]
    source_days = shift["total_source_days"]
    days = f"{source_days['numerator']}/{source_days['denominator']}"
    if source_days["denominator"] == 1:
        days = str(source_days["numerator"])
    return (
        f"[卷一百刻原式]\n{branches}各{long_ke}刻，其余各{ordinary}刻，合{profile['day_ke']}刻。每日添{literal['ke']}刻{literal['fen']}分的分制仍未核定。\n"
        f"以支初为相对原点，六日进一支的{shift['year_blocks']}块推演合{days}源日；日内添分和实际节月仍未接通。\n"
        f"原式未换成本次出生钟面或实际日卦日期；等时推算中的每刻{ratio}分不作原典默认值。"
    )
