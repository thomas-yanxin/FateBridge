"""Prepare a draft, register, seal and evaluate a pair-aware Sukuyo study.

No real samples or probabilities are fabricated. Files use exclusive creation.
"""

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.validation.predictions import Forecast, Outcome
from fatebridge.validation.sukuyo_study import (
    SukuyoProtocol,
    blind_outcome_sheet,
    evaluate,
    protocol_context_digest,
    register,
    seal_forecasts,
)


def read(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _publish_output(path: Path, raw: bytes) -> None:
    """Expose completed bytes exclusively; a failed write leaves no final file."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix="." + path.name + ".", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    draft = sub.add_parser("draft")
    context = sub.add_parser("context")
    context.add_argument("--protocol", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--protocol", required=True)
    reg.add_argument("--model", required=True)
    reg.add_argument("--artifact", action="append", required=True, metavar="NAME=PATH")
    seal = sub.add_parser("seal")
    seal.add_argument("--registration", required=True)
    seal.add_argument("--forecasts", required=True)
    seal.add_argument("--evidence", action="append", required=True, metavar="CASE=PATH")
    sheet = sub.add_parser("blind-sheet")
    sheet.add_argument("--registration", required=True)
    score = sub.add_parser("evaluate")
    score.add_argument("--registration", required=True)
    score.add_argument("--sealed", required=True)
    score.add_argument("--outcomes", required=True)
    score.add_argument(
        "--outcome-source", action="append", default=[], metavar="CASE=PATH"
    )
    for cmd in (draft, context, reg, seal, sheet, score):
        cmd.add_argument("--output", required=True)
    args = parser.parse_args()

    def files(items: list[str]) -> dict[str, bytes]:
        result = {}
        for item in items:
            if "=" not in item:
                parser.error("file bindings must use NAME=PATH")
            name, path = item.split("=", 1)
            if name in result:
                parser.error("duplicate file binding")
            result[name] = Path(path).read_bytes()
        return result

    now = datetime.now(timezone.utc)
    if args.action == "draft":
        result = {
            "status": "draft_not_registered",
            "real_world_sample_count": 0,
            "authority_certified": False,
            "protocol_schema": SukuyoProtocol.model_json_schema(),
            "required_decisions": [
                "固定单一关系场景、目标和未来观察窗口",
                "招募互不重叠的配对并声明全部训练主体",
                "依据独立资料冻结基线、概率映射、样本量和分析方案",
                "冻结实际历法、原典、解释及预测策略文件",
                "原始预测／结局以study_plan_sha256绑定含protocol_context_sha256的完整方案；不为旧记录补签",
                "窗口前将注册与预测承诺交独立可信时间戳存证",
                "裁定人员仅获得blind-sheet；到期后结局再揭盲",
            ],
            "scope": "草案与Schema不是已注册研究、真实样本或预测效力证据。",
        }
    elif args.action == "context":
        protocol = SukuyoProtocol.model_validate(read(args.protocol))
        result = {
            "status": "context_digest_only_not_registered",
            "format": "sukuyo_protocol_context_v1",
            "protocol_context_sha256": protocol_context_digest(protocol),
            "scope": "在注册和签发原始记录之前写入plan.protocol_context_sha256，再核验完整计划指纹；此命令不修改协议，不为旧记录补签。",
        }
    elif args.action == "register":
        result = register(
            SukuyoProtocol.model_validate(read(args.protocol)),
            Path(args.model).read_bytes(),
            at=now,
            artifacts=files(args.artifact),
        )
    elif args.action == "seal":
        result = seal_forecasts(
            read(args.registration),
            [Forecast.model_validate(f) for f in read(args.forecasts)],
            at=now,
            evidence=files(args.evidence),
        )
    elif args.action == "blind-sheet":
        result = blind_outcome_sheet(read(args.registration))
    else:
        result = evaluate(
            read(args.registration),
            read(args.sealed),
            [Outcome.model_validate(o) for o in read(args.outcomes)],
            at=now,
            outcome_sources=files(args.outcome_source),
        )
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    _publish_output(Path(args.output), raw.encode("utf-8"))
    print(
        json.dumps(
            {
                "action": args.action,
                "output": args.output,
                "authority_certified": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
