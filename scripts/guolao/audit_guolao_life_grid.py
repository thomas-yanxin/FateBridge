"""Read declared cells of Lu Wei's image78 grid without inferring a life degree."""

import argparse
import json

from fatebridge.core.guolao_grid import load_grid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--column", type=int)
    selection.add_argument("--source-marker", help="只查明确宿名标，不从普通格猜宿")
    parser.add_argument("--source-palace")
    parser.add_argument("--target-palace")
    attached = parser.add_mutually_exclusive_group()
    attached.add_argument("--marker-text", help="本图所见规范汉字附字，不是现代角度")
    attached.add_argument("--marker-not-visible", action="store_true")
    args = parser.parse_args()
    selector = args.column is not None or args.source_marker is not None
    if (
        args.source_palace is not None or args.target_palace is not None or selector
    ) and (args.source_palace is None or args.target_palace is None or not selector):
        parser.error("比较须明确来源宫支、目标宫支及原图列号或宿名标")
    has_attached = args.marker_text is not None or args.marker_not_visible
    if args.source_marker is not None and not has_attached:
        parser.error("宿标反查须明确--marker-text或--marker-not-visible，不补默认数")
    if args.source_marker is None and has_attached:
        parser.error("附字只与--source-marker一起使用")
    grid = load_grid()
    try:
        comparison = None
        if args.source_marker is not None:
            assert args.source_palace is not None and args.target_palace is not None
            comparison = grid.compare_marker(
                source_palace=args.source_palace,
                target_palace=args.target_palace,
                mansion=args.source_marker,
                attached_text=args.marker_text,
            )
        elif args.column is not None:
            assert args.source_palace is not None and args.target_palace is not None
            comparison = grid.compare(
                source_palace=args.source_palace,
                target_palace=args.target_palace,
                column=args.column,
            )
        result = {
            "audit": grid.audit(),
            "comparison": comparison,
        }
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
