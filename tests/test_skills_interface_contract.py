"""Conformance test for the machine-readable ``agents/interface.yaml`` contracts.

Each public ``skills/onda-*`` skill ships an ``agents/interface.yaml`` so an
agent runtime can discover the skill's scenario, the engine tools it drives, its
required inputs and output contract — without parsing prose. A second
description of a skill is only safe if it is *enforced*; an unchecked sidecar
would just become a new drift surface. This test locks each interface.yaml to
the FateBridge engine catalog and to the skill's own SKILL.md:

- ``engine_tools`` must equal exactly the CLI tools the SKILL.md documents
  (backticked ∩ catalog) — neither doc nor interface can drift from the other.
- ``dependencies`` declares shared support, conditional services and composite
  topics separately; its complete graph must resolve against the live catalog.
- ``required_inputs`` must be real request-model fields of the declared tools.
- ``name`` must match the directory and the SKILL.md frontmatter.
- ``reads`` must point at files that exist.

If a tool is renamed in the engine, or added to a SKILL.md without updating the
interface (or vice versa), CI fails here instead of an agent failing at runtime.
"""

import re
from pathlib import Path

import yaml

from fatebridge.application.description import spec_is_cli_safe
from fatebridge.services.tool_catalog import CATALOG

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / "skills"


def _project_license() -> str:
    # Regex (not tomllib) so it works identically on Python 3.10. Matches the
    # PEP 639 SPDX string form ``license = "Apache-2.0"``; anchored to line
    # start so it never catches ``license-files`` or an inline comment mention.
    text = (_REPO_ROOT / "pyproject.toml").read_text()
    return re.search(r'^license\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1).strip()


def _cli_specs_by_name() -> dict[str, object]:
    # Use the engine's own CLI-exposability rule (the single source of truth the
    # CLI itself uses to register commands) instead of re-deriving it. A private
    # copy here drifted: it recursed into ``list[Model]`` generics and wrongly
    # dropped tools the CLI actually exposes (e.g. ``sixyao``, whose optional
    # manual-toss ``lines: list[...]`` field is not a top-level nested model),
    # which silently exempted those tools from the interface contract.
    out: dict[str, object] = {}
    for spec in CATALOG:
        if not spec_is_cli_safe(spec):
            continue
        name = spec.mcp_name or spec.key
        if name:
            out[name] = spec
    return out


def _skill_dirs() -> list[Path]:
    return sorted(p for p in _SKILLS_ROOT.glob("onda-*") if (p / "SKILL.md").exists())


def _frontmatter_name(skill_md: Path) -> str:
    text = skill_md.read_text()
    body = re.search(r"^---\n(.*?)\n---", text, re.S).group(1)
    return re.search(r"^name:\s*(.+)$", body, re.M).group(1).strip()


def _documented_tools(skill_md: Path, cli_names: set[str]) -> set[str]:
    toks = set(re.findall(r"`([a-z][a-z0-9_]+)`", skill_md.read_text()))
    return toks & cli_names


def _load(skill_dir: Path) -> dict:
    return yaml.safe_load((skill_dir / "agents" / "interface.yaml").read_text())


def test_every_skill_has_an_interface_file():
    missing = [
        d.name for d in _skill_dirs() if not (d / "agents" / "interface.yaml").exists()
    ]
    assert not missing, f"skills missing agents/interface.yaml: {missing}"
    assert len(_skill_dirs()) >= 5


def test_interface_name_matches_dir_and_frontmatter():
    problems = []
    for d in _skill_dirs():
        iface = _load(d)
        fm = _frontmatter_name(d / "SKILL.md")
        if not (iface.get("name") == d.name == fm):
            problems.append(
                f"{d.name}: interface={iface.get('name')} dir={d.name} frontmatter={fm}"
            )
    assert not problems, "interface name mismatch:\n" + "\n".join(problems)


def test_interface_engine_tools_match_docs_and_catalog():
    cli_names = set(_cli_specs_by_name())
    problems = []
    for d in _skill_dirs():
        declared = set(_load(d).get("engine_tools") or [])
        if not declared:
            problems.append(f"{d.name}: empty engine_tools")
            continue
        not_real = sorted(declared - cli_names)
        if not_real:
            problems.append(f"{d.name}: engine_tools not in CLI catalog: {not_real}")
        documented = _documented_tools(d / "SKILL.md", cli_names)
        if declared != documented:
            problems.append(
                f"{d.name}: interface engine_tools != SKILL.md documented tools; "
                f"only-in-interface={sorted(declared - documented)} "
                f"only-in-doc={sorted(documented - declared)}"
            )
    assert not problems, "interface/engine/doc drift:\n" + "\n".join(problems)


def test_interface_required_inputs_are_real_fields():
    specs = _cli_specs_by_name()
    problems = []
    for d in _skill_dirs():
        iface = _load(d)
        tools = iface.get("engine_tools") or []
        valid_fields: set[str] = set()
        for t in tools:
            spec = specs.get(t)
            if spec is not None:
                valid_fields |= set(spec.request_model.model_fields)  # type: ignore[attr-defined]
        for field in iface.get("required_inputs") or []:
            if field not in valid_fields:
                problems.append(
                    f"{d.name}: required_input `{field}` is not a field of any declared tool"
                )
    assert not problems, "required_inputs drift:\n" + "\n".join(problems)


def test_interfaces_explicitly_declare_support_and_conditional_dependencies():
    from fatebridge.application.scenarios import dependency_closure
    from scripts.build_scenario_manifest import build_manifest

    bundle = build_manifest()
    records = {record["id"]: record for record in bundle["scenarios"]}
    resolved = dependency_closure(records, {spec.key for spec in CATALOG})
    for directory in _skill_dirs():
        interface = _load(directory)
        support = [
            dependency
            for dependency in interface["dependencies"]
            if dependency["kind"] == "shared_support"
        ]
        assert {"knowledge_registry", "knowledge_read"} <= {
            tool for dependency in support for tool in dependency.get("tools", [])
        }
        assert set(records[directory.name]["engine_tools"]) <= resolved[directory.name]
    # Safety-specific topics do not inherit unrelated personal timing services.
    for name in ("onda-jiankang", "onda-fengshui"):
        assert "profection" not in resolved[name]
        assert "astro_election" not in resolved[name]


def test_interface_license_matches_project():
    """Each skill's declared license must equal the project license — guards the
    exact MIT-vs-Apache drift found at publish prep (LICENSE said Apache-2.0
    while pyproject said MIT)."""
    expected = _project_license()
    problems = [
        f"{d.name}: license={_load(d).get('license')!r} != project {expected!r}"
        for d in _skill_dirs()
        if _load(d).get("license") != expected
    ]
    assert not problems, "interface license drift:\n" + "\n".join(problems)


def test_interface_reads_and_version_present():
    problems = []
    for d in _skill_dirs():
        iface = _load(d)
        if not str(iface.get("version") or "").strip():
            problems.append(f"{d.name}: missing version")
        # reads are written relative to the interface.yaml file itself
        # (i.e. the agents/ subdir), the standard "relative to declaring file".
        for rel in iface.get("reads") or []:
            target = (d / "agents" / rel).resolve()
            if not target.exists():
                problems.append(f"{d.name}: reads -> missing file {rel}")
    assert not problems, "interface reads/version issues:\n" + "\n".join(problems)


def test_codex_project_skill_entries_resolve_and_allow_discovery():
    """Project discovery must load the maintained package, including its refs."""
    for source in _skill_dirs():
        entry = _REPO_ROOT / ".agents" / "skills" / source.name
        assert entry.resolve() == source
        skill = entry / "SKILL.md"
        assert _frontmatter_name(skill) == entry.name
        metadata = yaml.safe_load((entry / "agents" / "openai.yaml").read_text())
        assert metadata.get("policy", {}).get("allow_implicit_invocation", True)
        interface = metadata["interface"]
        assert interface["display_name"]
        assert 25 <= len(interface["short_description"]) <= 64
        assert f"${entry.name}" in interface["default_prompt"]
        # References resolve from the actual discoverable path, not only the
        # source path. Catch copied/relocated packages with broken dependencies.
        for rel in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", skill.read_text()):
            if "://" not in rel:
                assert (entry / rel).exists(), (entry.name, rel)


def test_consultation_entries_cover_topics_services_and_compatible_composite():
    """Discovery distinguishes user topics from services without tool ownership."""
    from collections import Counter

    from fatebridge.application.scenarios import discover_scenarios, scenario_keys
    from fatebridge.core.consultation_policy import POLICY_ID

    interfaces = [_load(d) for d in _skill_dirs()]
    assert Counter(item["consultation"]["kind"] for item in interfaces) == {
        "topic": 9,
        "service": 3,
        "composite": 1,
    }
    expected = {
        "self",
        "career",
        "finance",
        "romance",
        "learning",
        "family",
        "social",
        "health_culture",
        "space",
    }
    assert {
        topic
        for item in interfaces
        if item["consultation"]["kind"] == "topic"
        for topic in item["consultation"]["topics"]
    } == expected
    for item in interfaces:
        assert item["consultation"]["scope"] == "current_question"
        assert item["consultation"]["safety_policy"] == POLICY_ID
    for topic in (
        "onda-shiye",
        "onda-caiwu",
        "onda-xueye",
        "onda-jiating",
        "onda-renji",
        "onda-yuanfen",
    ):
        tools = scenario_keys(CATALOG, topic)
        assert {
            "ziwei_birth",
            "astro_chart",
            "timing_analysis",
            "ziwei_horoscope",
            "western_timing_analysis",
            "firdaria",
        } <= tools
    # Topic filtering must retain its own cross-system and time capabilities.
    manifest = discover_scenarios(CATALOG, scenario="onda-caiwu", surface="mcp")
    assert manifest["consultation_policy"]["scope"] == "current_question"
    assert manifest["scenarios"][0]["consultation"]["kind"] == "topic"
    assert manifest["scenarios"][0]["availability"]["complete"]
