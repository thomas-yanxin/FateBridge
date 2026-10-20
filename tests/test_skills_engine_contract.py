"""Contract test guarding the public ``skills/`` suite against engine drift.

The Onda skills delegate every calculation to ``python3 -m fatebridge.cli
<tool>``; if a tool is renamed/removed in the catalog, or a newly added tool is
never surfaced to the skills, the docs silently drift out of sync with the
engine. The engine itself is covered by test_cli / test_full_surface_validation,
but nothing previously checked the skills docs against the catalog.

This asserts two contracts the project promises:

1. Coverage — every CLI-exposable tool is documented somewhere under ``skills/``.
2. Runnability — every *concrete* ``fatebridge.cli`` example in the docs uses
   only real flags of an existing CLI tool, and actually executes cleanly
   (exit 0). This makes the README's "提交前都要真跑一遍" promise an enforced
   gate instead of a human habit: the class of drift that bit us before
   (a flag renamed/removed in the engine, or a doc marking a required flag as
   optional) now fails CI instead of failing an agent at runtime.

Examples that contain placeholders (``<tool>``, ``...``, ``[...]``) are
illustrative, not runnable, and are skipped by design.
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

from tests.fixtures.catalog import cli_specs_by_name

_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"

# Global argparse flags the CLI adds on top of each tool's request model.
_GLOBAL_CLI_FLAGS = {
    "--no-metadata",
    "--fields",
    "--selected-sections",
    "--strict-fields",
    "--no-include-snapshot-text",
}

# Tokens that mark an example as a non-runnable template, not a real command.
_PLACEHOLDER_RE = re.compile(r"[<>\[\]]|\.\.\.")


def _cli_flags_for_spec(spec: object) -> set[str]:
    """Valid ``--flag`` set for a tool: one per request-model field, derived the
    same way the CLI does (``field_name`` -> ``--field-name``), plus globals."""
    flags = {
        "--" + name.replace("_", "-")
        for name in spec.request_model.model_fields  # type: ignore[attr-defined]
    }
    return flags | _GLOBAL_CLI_FLAGS


def _cli_tool_names() -> set[str]:
    return set(cli_specs_by_name())


def _skills_backticked_tokens() -> set[str]:
    text = "\n".join(p.read_text() for p in _SKILLS_ROOT.rglob("*.md"))
    return set(re.findall(r"`([a-z][a-z0-9_]+)`", text))


def _documented_cli_examples() -> list[tuple[Path, str, str, set[str]]]:
    """Parse fenced ```bash blocks across skills docs and return one entry per
    *concrete* fatebridge.cli invocation: (doc_path, tool, command, flags_used).

    Placeholder/template examples and the meta commands (``list``/``describe``)
    are excluded — only runnable commands are returned.
    """
    examples: list[tuple[Path, str, str, set[str]]] = []
    for md in sorted(_SKILLS_ROOT.rglob("*.md")):
        text = md.read_text()
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            joined = re.sub(r"\\\n\s*", " ", block)  # fold line continuations
            for raw in joined.splitlines():
                line = raw.strip()
                if "fatebridge.cli" not in line:
                    continue
                if " describe " in f" {line} " or re.search(r"\blist\b", line):
                    continue
                if _PLACEHOLDER_RE.search(line):
                    continue
                tokens = line.split()
                idx = tokens.index("fatebridge.cli")
                rest = [t for t in tokens[idx + 1 :] if t != "--no-metadata"]
                if not rest:
                    continue
                tool = rest[0]
                flags = set(re.findall(r"--[a-z0-9-]+", line))
                examples.append((md, tool, line, flags))
    return examples


def test_every_cli_tool_is_documented_in_skills():
    """No orphan tools: each CLI-exposable tool is referenced in skills docs."""
    documented = _skills_backticked_tokens()
    undocumented = sorted(t for t in _cli_tool_names() if t not in documented)
    assert not undocumented, (
        "These CLI tools exist in the catalog but no skill references them "
        f"(agents can't reach them): {undocumented}"
    )


def test_skills_root_is_present_and_nonempty():
    # Guard against the test silently passing if skills/ is moved or emptied.
    skill_files = list(_SKILLS_ROOT.rglob("SKILL.md"))
    assert len(skill_files) >= 5


def test_documented_examples_exist():
    # If the parser stops finding examples (docs restructured, fence style
    # changed), the runnability tests below would vacuously pass — guard that.
    assert len(_documented_cli_examples()) >= 10


def test_documented_cli_examples_use_real_flags():
    """Static gate (no engine execution, never flaky): every concrete example
    targets an existing CLI tool and uses only that tool's real flags."""
    specs = cli_specs_by_name()
    problems: list[str] = []
    for md, tool, line, flags in _documented_cli_examples():
        spec = specs.get(tool)
        if spec is None:
            problems.append(f"{md.name}: unknown / non-CLI tool `{tool}`")
            continue
        unknown = sorted(flags - _cli_flags_for_spec(spec))
        if unknown:
            problems.append(
                f"{md.name}: `{tool}` documented with flags the "
                f"engine doesn't accept: {unknown}"
            )
    assert not problems, "Skill docs drifted from engine CLI schema:\n" + "\n".join(
        problems
    )


def test_documented_cli_examples_run_clean():
    """Runnability gate: every concrete example actually executes (exit 0).

    The engine is fully offline and returns structured error payloads on stdout
    with a non-zero exit code, so exit 0 is the clean-run signal."""
    failures: list[str] = []
    for md, tool, line, _flags in _documented_cli_examples():
        command = shlex.split(line)
        assert command[0] in {"python", "python3"}, line
        command[0] = sys.executable
        proc = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            tail = (proc.stdout or proc.stderr).strip().replace("\n", " ")[:200]
            failures.append(f"{md.name}: `{tool}` exit={proc.returncode} :: {tail}")
    assert not failures, "Documented CLI examples failed to run:\n" + "\n".join(
        failures
    )
