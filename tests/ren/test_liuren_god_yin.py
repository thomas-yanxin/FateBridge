"""Primary yin-spirit examples and their distinct noble exception."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.liureng import build_liureng_board
from scripts.ren.audit_ren_classical import make_seed
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_god_yin_v1"
PIN = "884b06655608003346afc473daf704feff08de88c4a71a43174f5c99998ff30d"


def references():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(CORPUS / "freeze.json") == PIN
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert {p.name for p in CORPUS.iterdir()} == set(frozen["files"]) | {"freeze.json"}
    assert all(sha(CORPUS / n) == d for n, d in frozen["files"].items())
    return json.loads((CORPUS / "cases.json").read_text())


REF = references()


def symbolic_board(is_day=True, profile="tanyuan_xieji_v1"):
    return build_liureng_board(
        make_seed({"day": "甲子", "hour": "子", "month": "寅"}),
        month_general_override="申",
        is_diurnal_override=is_day,
        guiren_profile=profile,
    )


@pytest.mark.parametrize("case", REF["explicit_examples"], ids=lambda r: r["id"])
def test_all_four_explicit_book_lookups(case):
    board = symbolic_board(case.get("is_diurnal", True))
    assert "god_yin" in board, "The original yin-spirit calculation is absent"
    row = next(r for r in board["god_yin"]["rows"] if r["god"] == case["god"])
    for key in ("riding_branch", "yin_branch", "derivation"):
        assert row[key] == case[key]
    if "riding_earth_branch" in case:
        assert row["riding_earth_branch"] == case["riding_earth_branch"]


@pytest.mark.parametrize("case", REF["counterexamples"], ids=lambda r: r["id"])
def test_noble_exception_and_actual_riding_branch_are_not_intrinsic_house_lookup(case):
    row = next(
        r for r in symbolic_board()["god_yin"]["rows"] if r["god"] == case["god"]
    )
    assert row["yin_branch"] == case["correct_yin"]
    wrong = case.get("wrong_ordinary_yin", case.get("wrong_intrinsic_upper"))
    assert row["yin_branch"] != wrong


def test_default_profile_remains_declared_and_does_not_silently_take_book_nobles():
    common = symbolic_board(profile="liuren_common_v1")["god_yin"]
    selected = symbolic_board()["god_yin"]
    c = next(r for r in common["rows"] if r["god"] == "贵人")
    s = next(r for r in selected["rows"] if r["god"] == "贵人")
    assert (c["riding_branch"], c["yin_branch"]) == ("丑", "未")
    assert (s["riding_branch"], s["yin_branch"]) == ("未", "丑")
    assert common["guiren_profile"] == "liuren_common_v1"
    assert selected["guiren_profile"] == "tanyuan_xieji_v1"


@pytest.mark.parametrize("case", REF["synthetic_role_logic"])
def test_known_positive_missing_year_inputs_and_complete_negative_are_distinct(case):
    from fatebridge.core.metaphysics.liureng_god_yin import role_presence

    assert (
        role_presence(
            case["lesson"], case["transmission"], case["natal"], case["annual"]
        )
        is case["expected"]
    )


def test_original_paragraph_is_not_a_full_usability_or_prediction_verdict():
    evidence = symbolic_board()["god_yin"]
    assert len(evidence["rows"]) == 12
    noble = next(r for r in evidence["rows"] if r["god"] == "贵人")
    assert noble["lesson_indices"] == [] and noble["transmission_positions"] == []
    assert noble["in_natal_upper"] is noble["in_annual_upper"] is None
    assert noble["appears_in_roles"] is None
    assert all(r["comprehensive_eligibility"] is None for r in evidence["rows"])
    assert evidence["complete_classical_conformance"] is False


def test_selectable_snapshot_reports_each_actual_yin_without_certifying_usability():
    from fatebridge.services.metaphysics import calculate_liureng_gods

    payload = REST_POST_CASES[SPECS["liureng_gods"].rest_path]()
    payload["selected_sections"] = ["类神阴神"]
    result = calculate_liureng_gods(**payload)
    assert "error" not in result
    text = result["snapshot_text"]
    for row in result["liureng"]["god_yin"]["rows"]:
        assert (
            f"{row['god']}乘{row['riding_branch']}临{row['riding_earth_branch']}：阴神{row['yin_branch']}"
            in text
        )
    assert "类神综合可用性未裁" in text
    assert result["snapshot_export"]["selected_sections"] == ["类神阴神"]


def test_unknown_runyear_gender_keeps_known_natal_and_unknown_annual_membership():
    spec = SPECS["liureng_runyear"]
    payload = REST_POST_CASES[spec.rest_path]()
    payload["gender"] = "未知"
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    result = fn(*args, **kw)
    assert result["runyear"]["year_fate"]["annual"]["sky_branch"] is None
    natal = result["runyear"]["year_fate"]["natal"]["sky_branch"]
    assert natal is not None
    for row in result["liureng"]["god_yin"]["rows"]:
        assert row["in_natal_upper"] is (row["yin_branch"] == natal)
        assert row["in_annual_upper"] is None
        assert row["appears_in_roles"] is not False


def test_a_legitimate_partial_year_context_is_not_invented_or_required_complete():
    from fatebridge.core.output_liuren_god_yin import LiurenGodYin

    value = copy.deepcopy(symbolic_board()["god_yin"])
    del value["year_fate_uppers"]["annual"]
    assert LiurenGodYin.model_validate(value).model_dump(exclude_unset=True) == value


def test_omitted_projected_year_upper_is_not_a_false_unknown_assertion():
    spec = SPECS["liureng_runyear"]
    payload = REST_POST_CASES[spec.rest_path]()
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    result = fn(*args, **kw)
    for role in ["natal", "annual"]:
        del result["runyear"]["year_fate"][role]["sky_branch"]
    projected = spec.output_model.model_validate(result).model_dump(exclude_unset=True)
    assert projected["liureng"]["god_yin"] == result["liureng"]["god_yin"]


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_new_lookup_and_current_year_memberships_survive_three_ports(
    key, project, surface_calls
):
    spec = SPECS[key]
    payload = REST_POST_CASES[spec.rest_path]()
    # These are the repository's explicitly fictional test inputs, not data
    # inferred about the human user.
    fields = ["liureng.god_yin", "liureng.twelve_board", "liureng.meta"]
    if key == "liureng_runyear":
        fields.append("runyear.year_fate")
    if key == "sanshiunited":
        fields.append("subresults.liureng_gods.liureng.god_yin")
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, opts = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        opts.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, payload, params=params, options=opts, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in [http.json(), protocol.structured_content, cli]:
        evidence = body["liureng"]["god_yin"]
        assert len(evidence["rows"]) == 12
        if key == "liureng_runyear":
            yf = body["runyear"]["year_fate"]
            for row in evidence["rows"]:
                for role in ["natal", "annual"]:
                    upper = yf[role]["sky_branch"]
                    assert row[f"in_{role}_upper"] is (
                        None if upper is None else row["yin_branch"] == upper
                    )
        if key == "sanshiunited":
            assert evidence == body["subresults"]["liureng_gods"]["liureng"]["god_yin"]


def test_source_formula_faults_and_missing_complete_layer_are_rejected():
    from fatebridge.application.execution import OutputContractError, validate_output

    spec = SPECS["liureng_gods"]
    payload = REST_POST_CASES[spec.rest_path]()
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    good = fn(*args, **kw)
    for fault in ["yin_branch", "role", "missing", "source"]:
        bad = copy.deepcopy(good)
        if fault == "missing":
            del bad["liureng"]["god_yin"]
        elif fault == "source":
            next(
                t
                for t in bad["liureng"]["rule_trace"]
                if t["rule_id"] == "liuren.tanyuan_god_yin"
            )["source_url"] = "https://example.invalid/false-source"
        else:
            row = bad["liureng"]["god_yin"]["rows"][0]
            if fault == "yin_branch":
                row["yin_branch"] = "子" if row["yin_branch"] != "子" else "丑"
            else:
                row["appears_in_roles"] = not row["appears_in_roles"]
        with pytest.raises(OutputContractError):
            validate_output(spec, bad)


def test_internally_valid_but_unprovided_year_membership_cannot_be_invented():
    from fatebridge.application.execution import OutputContractError, validate_output
    from fatebridge.core.metaphysics.liureng_god_yin import add_year_fate_membership

    spec = SPECS["liureng_gods"]
    payload = REST_POST_CASES[spec.rest_path]()
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    result = fn(*args, **kw)
    add_year_fate_membership(
        result["liureng"],
        {"natal": {"sky_branch": "子"}, "annual": {"sky_branch": "丑"}},
    )
    with pytest.raises(OutputContractError):
        validate_output(spec, result)
