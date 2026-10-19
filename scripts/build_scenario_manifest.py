"""Generate bundled scenario definitions from existing interfaces and routing.

Run with the dev extra (PyYAML). Production reads only the generated JSON.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

from fatebridge.core.consultation_policy import POLICY_ID
from fatebridge.services.tool_catalog import CATALOG

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/fatebridge/data/agent_scenarios.json"


def build_manifest():
    routing_path = ROOT / "docs/scenario-routing.md"
    routing = routing_path.read_text()
    known = {name: spec.key for spec in CATALOG for name in (spec.key, spec.tool_name)}
    known["meihua"] = "meihua_analysis"  # documented compact table heading
    sources = {
        str(routing_path.relative_to(ROOT)): hashlib.sha256(
            routing_path.read_bytes()
        ).hexdigest()
    }
    for path in sorted((ROOT / "skills/_shared").glob("*.md")):
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    sections = re.split(
        r"^### ",
        routing.split("## 场景路由矩阵", 1)[1].split("## 长尾与专家级工具", 1)[0],
        flags=re.M,
    )[1:]

    def routes(section):
        headers = []
        rows = []
        for line in section.splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not headers:
                headers = cells
                continue
            if all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                continue
            selected = []
            for header, cell in zip(headers[1:], cells[1:]):
                role = {"主": "primary", "旁": "supporting", "深": "deep"}.get(cell[:1])
                if role:
                    tools = list(
                        dict.fromkeys(
                            known[token]
                            for token in re.findall(r"[a-z][a-z0-9_]*", header)
                            if token in known
                        )
                    )
                    if not tools:
                        raise ValueError(f"Unresolved route heading: {header}")
                    selected.append(
                        {
                            "role": role,
                            "alternatives": tools,
                            "condition": cell[1:].strip("（）"),
                        }
                    )
            rows.append({"intent": cells[0], "evidence": selected})
        return rows

    scenarios = []
    for path in sorted((ROOT / "skills").glob("onda-*/agents/interface.yaml")):
        source = yaml.safe_load(path.read_text())
        name = source["name"]
        section = next(s for s in sections if f"（{name}）" in s.splitlines()[0])
        scenarios.append(
            {
                "id": name,
                "name": source["scenario"],
                "version": source["version"],
                "summary": source["summary"],
                "consultation": source["consultation"],
                "triggers": source["triggers"],
                "engine_tools": [known[tool] for tool in source["engine_tools"]],
                "required_inputs": source["required_inputs"],
                "output": source["output"],
                "boundary": source["boundary"],
                "license": source["license"],
                "routing": routes(section),
                "source": str(path.relative_to(ROOT)),
            }
        )
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    home = next(s for s in sections if s.startswith("家居风水基础计算"))
    rows = []
    keys = []
    for line in home.splitlines():
        if not line.startswith("|") or "`fengshui_" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        key = re.search(r"`(fengshui_[a-z_]+)`", cells[1]).group(1)
        if key not in known:
            raise ValueError(f"Unknown home tool: {key}")
        if key not in keys:
            keys.append(key)
        rows.append(
            {
                "intent": cells[0],
                "evidence": [
                    {"role": "primary", "alternatives": [key], "condition": cells[2]}
                ],
            }
        )
    scenarios.append(
        {
            "id": "fengshui",
            "name": "家居风水基础计算",
            "version": "1.0",
            "summary": "住宅各层规则独立，明确参考北、住户与历史定运依据后选择工具",
            "consultation": {
                "kind": "calculation",
                "topics": ["space"],
                "scope": "current_question",
                "safety_policy": POLICY_ID,
            },
            "triggers": [row["intent"] for row in rows],
            "engine_tools": keys,
            "required_inputs": [],
            "output": {"kind": "calculation", "grounding": "engine_fields"},
            "boundary": "基础层及已定版本玄空规则；不从户型图猜测缺失测量，不推断其他门派。",
            "routing": rows,
            "source": "docs/scenario-routing.md",
        }
    )
    return {
        "schema_version": "1.0",
        "sources_sha256": sources,
        "consultation_policy": {
            "id": POLICY_ID,
            "routing": "topic_task_time_scope",
            "scope": "current_question",
            "integration": "additional_relevant_evidence_not_tool_quota",
            "follow_up": "retain_topic_and_reuse_unchanged_results",
            "boundaries": "skills/_shared/safety-boundaries.md",
            "time_selection": "skills/_shared/timing-selection.md",
        },
        "scenarios": scenarios,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != rendered:
            raise SystemExit(
                "Scenario manifest is stale; run scripts/build_scenario_manifest.py"
            )
    else:
        TARGET.write_text(rendered)


if __name__ == "__main__":
    main()
