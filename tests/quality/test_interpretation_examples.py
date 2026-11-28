"""Keep migrated technical-reference CLI examples runnable against the catalog."""

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import pytest

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.cli import build_parser as build_cli_parser
from fatebridge.cli import run as cli_run
from fatebridge.services.tool_catalog import CATALOG

REFERENCES_ROOT = Path(__file__).resolve().parents[2] / "docs/interpretation"

# note (cli): These global flags are accepted independently of the tool request model.
GLOBAL_CLI_FLAGS = {
    "--include",
    "--fields",
    "--as-of",
    "--request-file",
}

PLACEHOLDER_RE = re.compile(r"[<>\[\]]|\.\.\.")


@dataclass(frozen=True, kw_only=True)
class CliExample:
    path: Path
    tool_name: str
    command: str
    flags: set[str]


def cli_flags_for_spec(spec: ToolSpec) -> set[str]:
    flags = {
        "--" + field_name.replace("_", "-")
        for field_name in spec.request_model.model_fields
    }
    return flags | GLOBAL_CLI_FLAGS


def documented_cli_examples() -> list[CliExample]:
    """Read concrete CLI tool commands from the method-reference Bash fences."""
    examples: list[CliExample] = []
    for path in sorted(REFERENCES_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            joined = re.sub(r"\\\n\s*", " ", block)
            for raw in joined.splitlines():
                line = raw.strip()
                if "fatebridge.cli" not in line:
                    continue
                else:
                    pass
                if " describe " in f" {line} " or re.search(r"\blist\b", line):
                    continue
                else:
                    pass
                if PLACEHOLDER_RE.search(line):
                    continue
                else:
                    pass
                tokens = line.split()
                module_position = tokens.index("fatebridge.cli")
                rest = tokens[module_position + 1 :]
                if not rest:
                    continue
                else:
                    pass
                tool = rest[0]
                flags = set(re.findall(r"--[a-z0-9-]+", line))
                examples.append(
                    CliExample(path=path, tool_name=tool, command=line, flags=flags)
                )
    return examples


def test_documented_examples_exist() -> None:
    """Catch reference changes that would leave the execution gate with no input."""
    assert len(documented_cli_examples()) >= 10


def test_documented_cli_examples_use_real_flags() -> None:
    """Check that concrete commands use published tool names and flags."""
    specs = {spec.name: spec for spec in CATALOG}
    problems: list[str] = []
    for example in documented_cli_examples():
        spec = specs.get(example.tool_name)
        if spec is None:
            problems.append(
                f"{example.path.name}: unknown / non-CLI tool {example.tool_name}"
            )
            continue
        else:
            pass
        unknown = sorted(example.flags - cli_flags_for_spec(spec))
        if unknown:
            problems.append(
                f"{example.path.name}: {example.tool_name} documented with flags the "
                f"engine doesn't accept: {unknown}"
            )
        else:
            pass
    assert (
        not problems
    ), "Method references drifted from engine CLI schema:\n" + "\n".join(problems)


@pytest.mark.parametrize(
    "example",
    {
        tuple(shlex.split(example.command))[1:]: example
        for example in documented_cli_examples()
    }.values(),
    ids=lambda example: f"{example.path.name}-{example.tool_name}",
)
def test_documented_cli_examples_run_clean(
    example: CliExample, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run the documented command or parse charts that have separate slow tests."""
    command = shlex.split(example.command)
    assert command[:3] in (
        ["python", "-m", "fatebridge.cli"],
        ["python3", "-m", "fatebridge.cli"],
    ), example.command
    if example.tool_name in {
        "horary_chart",
        "evaluate_election_time",
    }:
        parsed = build_cli_parser().parse_args(command[3:])
        assert parsed._spec.name == example.tool_name
        return
    else:
        pass
    capsys.readouterr()
    code = cli_run(command[3:])
    captured = capsys.readouterr()
    tail = (captured.out or captured.err).strip().replace("\n", " ")[:200]
    assert code == 0, f"{example.path.name}: {example.tool_name} exit={code} :: {tail}"
