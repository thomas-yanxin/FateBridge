"""逐项对照卷45六个争议格的馆藏扫描；不裁定或更改计算底本。"""

import argparse
import json

from fatebridge.validation.guolao_witnesses import audit_gujin45_witness_variants


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targeted-audit", action="store_true", required=True)
    parser.parse_args()
    print(
        json.dumps(
            audit_gujin45_witness_variants(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
