"""Western events tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import CompactView, ServiceResult, ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_events"


def _compact_horary_actor(actor: object) -> object:
    if not isinstance(actor, dict):
        return actor
    ha = actor.get("house_assignment")
    hc = actor.get("house_condition")
    ec = actor.get("essential_condition")
    out: ServiceResult = {
        k: v
        for k, v in actor.items()
        if k
        in {
            "house",
            "planet",
            "planet_label",
            "sign",
            "sign_label",
            "degree",
            "longitude",
            "speed",
            "retrograde",
            "occupied_house",
            "dignities",
        }
    }
    if isinstance(ha, dict):
        out["assigned_house"] = ha.get("assigned_house")
    if isinstance(hc, dict):
        out["house_class"] = hc.get("house_class")
    if isinstance(ec, dict):
        out["essential_condition"] = {
            k: v
            for k, v in ec.items()
            if k in {"dignities", "debilities", "peregrine", "lords"}
        }
    return out


def _compact_reception(rec: object) -> object:
    if not isinstance(rec, dict):
        return rec
    dirs = rec.get("directions")
    compact_dirs = (
        [
            {
                k: v
                for k, v in d.items()
                if k
                in {
                    "receiver",
                    "guest",
                    "guest_sign",
                    "dignities",
                    "unknown_dignities",
                    "receives",
                }
            }
            for d in dirs
            if isinstance(d, dict)
        ]
        if isinstance(dirs, list)
        else dirs
    )
    return {
        "status": rec.get("status"),
        "mutual": rec.get("mutual"),
        "mutual_same_kind": rec.get("mutual_same_kind"),
        "directions": compact_dirs,
    }


def _compact_horary(result: ServiceResult) -> ServiceResult:
    horary = result.get("horary_chart")
    if not isinstance(horary, dict):
        return result
    moon = horary.get("moon") or {}
    rad = horary.get("radicality") or {}
    fort = horary.get("fortitudes") or {}
    perf = horary.get("perfection") or {}
    sigs = horary.get("significators") or {}
    fortune = horary.get("fortune") or {}
    hour_aff = rad.get("hour_affinity") or {}
    compact_horary = {
        "system": horary.get("system"),
        "category": horary.get("category"),
        "quesited_house": horary.get("quesited_house"),
        "turned_from_house": horary.get("turned_from_house"),
        "turned_house": horary.get("turned_house"),
        "ascendant": horary.get("ascendant"),
        "significators": {
            "querent": _compact_horary_actor(sigs.get("querent")),
            "quesited": _compact_horary_actor(sigs.get("quesited")),
            "moon_co_significator": _compact_horary_actor(
                sigs.get("moon_co_significator")
            ),
            "directed_sign_relationship": sigs.get("directed_sign_relationship"),
        },
        "moon": {
            "sign": moon.get("sign"),
            "sign_label": moon.get("sign_label"),
            "speed": moon.get("speed"),
            "void_of_course": moon.get("void_of_course"),
            "degrees_left_in_sign": moon.get("degrees_left_in_sign"),
            "next_aspect": moon.get("next_aspect"),
        },
        "radicality": {
            "safe_to_judge": rad.get("safe_to_judge"),
            "status": rad.get("status"),
            "hour_affinity": (
                {
                    k: hour_aff.get(k)
                    for k in (
                        "hour_ruler",
                        "ascendant_lord",
                        "same_ruler",
                        "ascendant_triplicity",
                        "same_own_nature",
                        "supported_under_declared_policy",
                    )
                }
                if isinstance(hour_aff, dict)
                else hour_aff
            ),
            "strictures": [
                {
                    k: v
                    for k, v in s.items()
                    if k in {"code", "status", "exception_satisfied", "detail"}
                }
                for s in (rad.get("strictures") or [])
                if isinstance(s, dict)
            ],
            "ascendant_degree_gate": rad.get("ascendant_degree_gate"),
            "unknown_clauses": rad.get("unknown_clauses"),
        },
        "fortitudes": {
            "summary": {
                p: {
                    "status": data.get("status"),
                    "known_fortitudes": data.get("known_fortitudes"),
                    "known_debilities": data.get("known_debilities"),
                    "known_balance": data.get("known_balance"),
                    "literal_table_balance": data.get("literal_table_balance"),
                    "unknown_rows": data.get("unknown_rows"),
                    **(
                        {
                            "applied_codes": [
                                f"{r['code']}({r['contribution']:+d})"
                                for r in (data.get("applied_conditions") or [])
                                if isinstance(r, dict)
                            ]
                        }
                        if isinstance(data.get("applied_conditions"), list)
                        else {}
                    ),
                }
                for p, data in (fort.get("summary") or {}).items()
                if isinstance(data, dict)
            },
        },
        "fortune": (
            {
                k: v
                for k, v in fortune.items()
                if k
                in {
                    "sign",
                    "degree_in_sign",
                    "longitude",
                    "solar_state",
                    "bound_lord",
                    "known_fortitudes",
                    "known_debilities",
                    "known_balance",
                }
            }
            if isinstance(fortune, dict)
            else fortune
        ),
        "chart_almuten": (
            {
                k: v
                for k, v in (horary.get("chart_almuten") or {}).items()
                if k in {"winner", "winners", "total_scores", "scores"}
            }
            if isinstance(horary.get("chart_almuten"), dict)
            else horary.get("chart_almuten")
        ),
        "antiscia_contacts": horary.get("antiscia_contacts"),
        "perfection": {
            "perfected": perf.get("perfected"),
            "status": perf.get("status"),
            "before_ingress": perf.get("before_ingress"),
            "intervening_contacts_count": perf.get("intervening_contacts_count"),
            "sequence_conditions_unverified": perf.get(
                "sequence_conditions_unverified"
            ),
            "perfection_routes": perf.get("perfection_routes"),
            "obstructions": perf.get("obstructions"),
            "principal_reception": _compact_reception(perf.get("principal_reception")),
            "event_path_summary": perf.get("event_path_summary"),
        },
    }
    return {
        "analysis_type": result.get("analysis_type"),
        "analysis_context": result.get("analysis_context"),
        "horary_chart": compact_horary,
        "summary": result.get("summary"),
        **(
            {"run_metadata": result["run_metadata"]} if "run_metadata" in result else {}
        ),
    }


def _compact_election(result: ServiceResult) -> ServiceResult:
    el = result.get("election")
    if not isinstance(el, dict):
        return result
    moon = el.get("moon") or {}
    compact_el = {
        "topic_id": el.get("topic_id"),
        "topic_house": el.get("topic_house"),
        "significator": el.get("significator"),
        "ascendant": el.get("ascendant"),
        "moon": {
            "sign": moon.get("sign"),
            "void_of_course": moon.get("void_of_course"),
            "next_applying_aspect": moon.get("next_applying_aspect"),
            "phase": moon.get("phase"),
            "solar_condition": moon.get("solar_condition"),
        },
        "planetary_hour_match": el.get("planetary_hour_match"),
        "planetary_hour": el.get("planetary_hour"),
        "factors": el.get("factors"),
        "unresolved_factors": el.get("unresolved_factors"),
        **(
            {"candidate_windows": el["candidate_windows"]}
            if "candidate_windows" in el
            else {}
        ),
    }
    return {
        "analysis_type": result.get("analysis_type"),
        "analysis_context": result.get("analysis_context"),
        "election": compact_el,
        "summary": result.get("summary"),
        **(
            {"run_metadata": result["run_metadata"]} if "run_metadata" in result else {}
        ),
    }


calculate_election = service_ref(
    "fatebridge.services.western_election", "calculate_election"
)


calculate_extrareturns = service_ref(
    "fatebridge.services.western_events", "calculate_extrareturns"
)


calculate_mundane = service_ref(
    "fatebridge.services.western_events", "calculate_mundane"
)


calculate_horary = service_ref("fatebridge.services.western_horary", "calculate_horary")


def _western_event_spec(
    name: str,
    service: ServiceRef,
    model_name: str,
    label: str,
    *,
    compact_view: CompactView | None = None,
) -> ToolSpec:
    """Register a western ephemeris-event technique (ingress chart / planetary return)."""
    return ToolSpec(
        name=name,
        bind=bind_kwargs(service),
        request_model_loader=request_model_ref(_REQ_MODULE, model_name),
        summary=(
            "按明确提问时刻起盘，核算月亮出宫前黄经事件与原典条件；禁生死/疾病/生育判断。"
            if name == "horary_chart"
            else (
                "按明确候选时刻起盘评估非医疗活动条件（支持窗口搜索）。"
                if name == "evaluate_election_time"
                else f"生成{label}（求解天文时刻后起盘）。"
            )
        ),
        operation_label_zh=label,
        family="western_event",
        cpu_bound=True,
        rest_path="/api/astrology/events/" + name.replace("_", "-"),
        cli_request_file=name == "horary_chart",
        compact_view=compact_view,
    )


SPECS: list[ToolSpec] = [
    _western_event_spec(
        "mundane_ingress_chart",
        calculate_mundane,
        "AstroMundaneRequest",
        "世俗入宫盘",
    ),
    _western_event_spec(
        "planetary_returns",
        calculate_extrareturns,
        "AstroExtraReturnsRequest",
        "多重回归",
    ),
    _western_event_spec(
        "horary_chart",
        calculate_horary,
        "AstroHoraryRequest",
        "卜卦证据",
        compact_view=_compact_horary,
    ),
    _western_event_spec(
        "evaluate_election_time",
        calculate_election,
        "AstroElectionRequest",
        "择日",
        compact_view=_compact_election,
    ),
]
