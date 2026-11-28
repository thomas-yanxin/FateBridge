"""Exercise documentation checks with broken and valid authoring examples."""

import json
from pathlib import Path

import pytest

from fatebridge.services.tool_catalog import CATALOG
from scripts import check_docs


def test_fences_do_not_create_headings_or_links() -> None:
    document = check_docs.inspect_markdown(
        '# 标题 `fields`\n\n```json\n{"sample": "[x](missing.md)"}\n```\n'
        "\n# 标题 `fields`\n`[literal](missing.md)`\n"
    )
    assert document.anchors == {"标题-fields", "标题-fields-1"}
    assert document.links == []
    assert document.json_blocks == 1
    assert document.errors == []


def test_explicit_html_ids_are_link_targets_outside_literal_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(
        '[section](#source-axis)\n<a\n id="source-axis"></a>\n'
        '<h2 id="named-heading">Heading</h2>\n'
        '`<a id="inline-code"></a>`\n'
        '```html\n<a id="fenced-code"></a>\n```\n',
        encoding="utf-8",
    )
    document = check_docs.inspect_markdown((tmp_path / "README.md").read_text())
    assert document.anchors == {"source-axis", "named-heading"}
    assert check_docs.main([]) == 0
    with (tmp_path / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("[literal](#fenced-code)\n")
    assert check_docs.main([]) == 1


@pytest.mark.parametrize(
    "text,expected",
    [
        ("```json\n{bad}\n```", "invalid JSON"),
        ("~~~python\nprint('example')", "unclosed code fence"),
        ("````python\n```\n", "unclosed code fence"),
    ],
)
def test_invalid_fences_and_json_report_opening_line(text: str, expected: str) -> None:
    document = check_docs.inspect_markdown(text)
    assert document.errors[0].startswith("1:")
    assert expected in document.errors[0]


def test_local_links_encoded_paths_and_badges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(
        "[part](docs/a%20b.md#标题-fields)\n"
        "[duplicate](docs/a%20b.md#标题-fields-1)\n"
        "[![badge](https://example.com/badge.svg)](LICENSE)\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a b.md").write_text(
        "# 标题 `fields`\n\n# 标题 `fields`\n", encoding="utf-8"
    )
    (tmp_path / "LICENSE").touch()
    monkeypatch.chdir(tmp_path.parent)
    assert check_docs.main([]) == 0


@pytest.mark.parametrize(
    "text,expected",
    [
        ("[missing](missing.md)", "missing local target"),
        ("[anchor](#absent)", "missing heading anchor"),
        ("[![badge](https://example.com/b.svg)](absent)", "missing local target"),
    ],
)
def test_broken_links_fail_with_source_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str,
    expected: str,
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(text, encoding="utf-8")
    assert check_docs.main([]) == 1
    assert f"README.md:1: {expected}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name",
    [
        "docs/examples/broken.json",
        "docs/examples/study/broken.json",
        "examples/study/broken.json",
    ],
)
def test_invalid_example_json_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    example: Path = tmp_path / name
    example.parent.mkdir(parents=True)
    example.write_text("{broken}", encoding="utf-8")
    assert check_docs.main([]) == 1
    assert f"{name}: invalid JSON" in capsys.readouterr().out


def test_interpretation_docs_are_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    path = tmp_path / "docs/interpretation/shared/reference.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[retired entry](missing.md)\n", encoding="utf-8")
    assert check_docs.main([]) == 1
    output = capsys.readouterr().out
    assert "docs/interpretation/shared/reference.md:1: missing local target" in output


def test_current_links_to_missing_historical_files_or_anchors_still_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    archive = tmp_path / "docs/validation"
    archive.mkdir(parents=True)
    (archive / "report.md").write_text("# 存在的标题\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[缺文件](docs/validation/missing.md)\n"
        "[缺标题](docs/validation/report.md#absent)\n",
        encoding="utf-8",
    )
    assert check_docs.main([]) == 1
    output = capsys.readouterr().out
    assert "missing local target" in output
    assert "missing heading anchor" in output


def test_reference_links_and_multiline_html_keep_source_locations() -> None:
    document = check_docs.inspect_markdown(
        "[guide][Getting Started]\n![logo][logo]\n[logo][]\n"
        '<a\n href="docs/start.md#setup">Start</a>\n'
        '<img src="images/logo.png">\n'
        '```html\n<img src="not-an-asset.png">\n```\n'
        '[getting started]: <docs/start.md#setup> "Setup"\n'
        "[logo]: images/logo.png\n[missing][unknown]\n"
    )
    assert document.links == [
        (4, "docs/start.md#setup"),
        (6, "images/logo.png"),
        (1, "docs/start.md#setup"),
        (2, "images/logo.png"),
        (3, "images/logo.png"),
    ]
    assert document.errors == ["12: undefined link reference: unknown"]


@pytest.mark.parametrize(
    "text",
    ['<img src="missing.png">', "[logo][asset]\n\n[asset]: missing.png"],
)
def test_missing_html_and_reference_assets_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(text, encoding="utf-8")
    assert check_docs.main([]) == 1


EXAMPLE_TOOL_MAP = {
    "examples/demo-subject.json": "astrology_chart",
    "docs/examples/fengshui-home.json": "fengshui_assess",
    "docs/examples/fengshui-xuankong.json": "fengshui_xuankong_house_chart",
    "docs/examples/liuyao-conditional-demo.json": "liuyao",
}

RETIRED_DOC_SYMBOLS = (
    "discover_capabilities",
    "describe_capability",
    "read_result",
    "detail=standard",
    'detail="standard"',
    "selected_sections",
    "snapshot_export",
    "result_delivery",
    "projection_warnings",
    "desktop_bagua_btb_v1",
    "user_expert_policy_v1",
    "workstation_layout",
    "surface_layouts",
    "environmental_context",
    "analysis_progress",
    "unsupported_queries",
)

PLAN_A_RETIRED_DOC_SYMBOLS = (
    "detail=compact",
    'detail="compact"',
    "detail=audit",
    'detail="audit"',
    "--detail compact",
    "--detail audit",
    "?detail=compact",
    "?detail=audit",
    "compact_fields",
    "compact_view",
    "detail_view",
    "rule_trace",
    "source_citations",
    "source_catalog",
)


def test_example_json_files_validate_against_live_request_models() -> None:
    """Every published JSON example maps to a live tool and validates cleanly."""
    root = check_docs.ROOT
    discovered = {
        path.relative_to(root).as_posix()
        for folder in (root / "examples", root / "docs" / "examples")
        for path in folder.rglob("*.json")
    }
    assert discovered == set(EXAMPLE_TOOL_MAP)
    specs = {spec.name: spec for spec in CATALOG}
    for rel_path, tool_name in sorted(EXAMPLE_TOOL_MAP.items()):
        payload = json.loads((root / rel_path).read_text(encoding="utf-8"))
        specs[tool_name].request_model.model_validate(payload)


def test_maintained_docs_contain_no_retired_api_symbols() -> None:
    """Maintained Markdown pages must not reintroduce retired APIs or fields."""
    hits: list[str] = []
    for path in check_docs.markdown_paths():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(check_docs.ROOT)
        symbols = RETIRED_DOC_SYMBOLS + (
            PLAN_A_RETIRED_DOC_SYMBOLS if path.name != "CHANGELOG.md" else ()
        )
        for symbol in symbols:
            if symbol in text:
                hits.append(f"{rel}: {symbol}")
    assert not hits, "Found retired symbols in maintained docs:\n" + "\n".join(hits)


def test_interpretation_schema_paths_valid_and_rejects_stale_qimen_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_docs.check_interpretation_schema_paths() == []
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    qimen_doc = tmp_path / "docs/interpretation/zhanbu/qimen-evidence.md"
    qimen_doc.parent.mkdir(parents=True, exist_ok=True)
    qimen_doc.write_text(
        "# 奇门盘面证据\n\n宫内读取 `evidence.door_palace_relation` 与 `qualification.door_palace_evidence`。\n",
        encoding="utf-8",
    )
    assert check_docs.main([]) == 1
    out = capsys.readouterr().out
    assert "evidence.door_palace_relation" in out
    assert "qualification.door_palace_evidence" in out


STALE_INTERPRETATION_SYMBOLS: tuple[str, ...] = (
    "stage_variants",
    "natal_ruler_contexts",
    "moon_readings",
    "timezone_basis",
    "configuration_not_supported",
    "wealth_components",
    "research_validation",
    "additional_profile_audits",
    "time_scope_comparison",
    "current_profile_study",
    "reference_baseline_supplement",
    "selected_readings.source_witnesses",
    "ziwei_birth.limit_reading",
    "source_comparison.matches_source_record",
    "ephemeris_provenance",
    "native_execution_context",
    "ephemeris_source_summary",
    "guolao_research_v7",
    "source_consistency.channel_classifications",
    "cycle_summary.reference_ordering",
    "cycle_context.reference_ordering",
    "cycle_summary.reference_contact_ordering",
    "design_solver.numerical_precision.design_body_endpoint_assessment",
    "design_body_endpoint_summary.interpretation_summary",
    "design_body_endpoint_assessment.endpoint_interpretations",
    "cycle_summary.numerical_scope",
    "apparent_position_context.coordinate_context",
    "interpretation.coordinate_frame_meaning",
    "station_witnesses[*].coordinate_probe",
    "motion_evidence.search_segment_phase_trend",
    "ziwei_rules.rule_catalogue.sihua_source_comparison",
    "calendar_basis.date_conversion_provenance",
    "critical_calendar_reference.image_witness_research",
    "calendar_reference.edo_calendar_method_reference",
    "validation.sukuyo.verify_sukuyo_context_claims",
    "chart_variant=germany",
    "hinoo_source",
    "printed_edition_reference",
    "purple_model_audit",
    "active_primary_evidence",
    "downloaded_primary_edition",
    "cached_primary_excerpt",
    "manuscript_month_header",
    "manuscript_daily_annotations",
    "include_calculation_reading",
    "calculation_reading",
    "gate_activation_context",
    "local_root_family_summary",
    "numerical_precision",
    "natal_palace_ganzhi",
    "natal_star_label",
    "midpoint_analysis.time_sensitivity",
    "liureng.month_general",
    "liureng.branch_relations",
    "附带 liureng 盘",
    "scopes.palace_name",
    "palace_map.scope_palace_name",
    "ziwei_horoscope.calendar_basis.time_input",
    "activations[*].ephemeris_model",
    "selected_record_paths",
    "options_applied",
    "enclosure_assessment",
    "count_source_assessment",
    "elemental_guan_assessment",
    "reading_guide",
    "nonphysical_factor_models",
    "native_return_flags",
    "source_dangwei",
    "najia_collation",
    "candidate_mansion_days",
    "clock_evaluation_status",
    "source_day_evidence",
    "birth_pada_established",
    "complete_calendar_assessment",
    "chart.params.chart_profile.longitude_motion",
    "source_clock",
    "physical_clock_applied",
    "calendar_mapping_complete",
    "hexagram_entry",
    "pure_trigram_rule",
    "source_issues",
    "not_adjudicated",
    "profile.input_clock",
    "source_hour_count_with_declared_research_inputs_v1",
    "guolao_month_basis",
    "source_name_mapping",
    "unresolved_from_source",
    "completely_open",
    "conditional_only",
    "hypothetical_element_source",
    "seorbel.txt",
)


def test_guidance_and_interpretation_docs_have_no_stale_r4_symbols() -> None:
    """Prevent regression of retired R4 call_guidance, contract, and interpretation doc paths."""
    root = check_docs.ROOT
    agent_examples_path = root / "src" / "fatebridge" / "data" / "agent_examples.json"
    agent_examples_text = agent_examples_path.read_text(encoding="utf-8")
    agent_examples = json.loads(agent_examples_text)
    hits: list[str] = [
        f"agent_examples.json: {sym}"
        for sym in STALE_INTERPRETATION_SYMBOLS
        if sym in agent_examples_text
    ]
    for tool_name in ("vedic_chart", "vimshottari_dasha", "human_design"):
        cg_text = json.dumps(
            agent_examples.get("call_guidance", {}).get(tool_name, {}),
            ensure_ascii=False,
        )
        for sym in ("ephemeris_model_scope", "nonphysical_factor_models"):
            if sym in cg_text:
                hits.append(f"agent_examples.json call_guidance.{tool_name}: {sym}")
    heluo_cg_text = json.dumps(
        agent_examples.get("call_guidance", {}).get("heluo", {}),
        ensure_ascii=False,
    )
    if "cycleYear" in heluo_cg_text:
        hits.append("agent_examples.json call_guidance.heluo: cycleYear")
    guolao_cg_text = json.dumps(
        agent_examples.get("call_guidance", {}).get("guolao_chart", {}),
        ensure_ascii=False,
    )
    if "longitude_speed_native" in guolao_cg_text:
        hits.append(
            "agent_examples.json call_guidance.guolao_chart: longitude_speed_native"
        )
    for path in sorted((root / "docs" / "interpretation").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        for sym in STALE_INTERPRETATION_SYMBOLS:
            if sym in text:
                hits.append(f"{rel}: {sym}")
        if path.name in {"vedic-evidence.md", "human-design.md"}:
            for sym in ("ephemeris_model_scope", "nonphysical_factor_models"):
                if sym in text:
                    hits.append(f"{rel}: {sym}")
        if path.name == "numerology.md" and "cycleYear" in text:
            hits.append(f"{rel}: cycleYear")
        if path.name in {"sukuyo-evidence.md", "fatebridge-engine.md"}:
            for sym in ("`conflicted`", "`uncovered`"):
                if sym in text:
                    hits.append(f"{rel}: {sym}")
    vedic_doc = (
        root / "docs" / "interpretation" / "shared" / "vedic-evidence.md"
    ).read_text(encoding="utf-8")
    assert "total_virupa` 为 `null`" not in vedic_doc
    assert "total_virupa 为 null" not in vedic_doc

    import re

    assert not re.search(
        r"(?<![a-z_])profile\.anchor_longitude", agent_examples_text
    ), "agent_examples.json still cites unqualified profile.anchor_longitude"
    hamburg_doc = (
        root / "docs" / "interpretation" / "xingpan" / "hamburg-evidence.md"
    ).read_text(encoding="utf-8")
    assert not re.search(
        r"(?<![a-z_])time_sensitivity\.source_pattern\.sampled_status", hamburg_doc
    ), "hamburg-evidence.md still cites time_sensitivity.source_pattern.sampled_status"
    assert "birth_time_uncertainty_minutes" in hamburg_doc
    assert "swisseph_fictitious_elements" in hamburg_doc
    comparative_when = (
        agent_examples.get("evidence_views", {})
        .get("hamburg_midpoint_chart", {})
        .get("comparative_geometry", {})
        .get("when", "")
    )
    assert "birth_time_uncertainty_minutes" in comparative_when, (
        "hamburg_midpoint_chart.evidence_views.comparative_geometry.when must "
        "explicitly document birth_time_uncertainty_minutes"
    )
    for contract_path in sorted((root / "docs" / "contracts").glob("*.json")):
        contract_text = contract_path.read_text(encoding="utf-8")
        for sym in ("hypothetical_element_source", "seorbel.txt"):
            if sym in contract_text:
                hits.append(f"{contract_path.relative_to(root)}: {sym}")
    guolao_doc = (
        root / "docs" / "interpretation" / "xingpan" / "guolao-evidence.md"
    ).read_text(encoding="utf-8")
    assert "guolao.profile.time_conversion" in guolao_doc
    assert "life_palace.clock_basis" in guolao_doc
    assert "地方平太阳时" not in guolao_doc
    liuren_board_py = (
        root / "src" / "fatebridge" / "core" / "contracts" / "output_liuren_board.py"
    ).read_text(encoding="utf-8")
    assert "liureng.branch_relations" not in liuren_board_py
    assert not hits, "Found stale R4/R5 symbols:\n" + "\n".join(hits)
