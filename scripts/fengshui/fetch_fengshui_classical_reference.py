"""Freeze literal numeric clauses from identified classical transcriptions.

No production tables, algorithms or generated expected charts are imported.
This records a web transcription, not a collated original print edition.
"""

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = {
    "shen": "https://www.diancangwang.cn/xuanxuewushu/f6f37803664b/90b563d9cb41.html",
    "you-nian": "https://bazhaimingjing.5000yan.com/64912.html",
}
BAZHAI_DEPTH_SOURCES = {
    "you_nian_origin": "https://bazhaimingjing.5000yan.com/23/",
    "fuwei_context": "https://bazhaimingjing.5000yan.com/64996.html",
}
NUMERALS = "一二三四五六七八九"


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(raw):
    parser = TextParser()
    parser.feed(raw.decode("utf-8"))
    return "\n".join(parser.parts)


def parse_shen(text):
    heads = list(re.finditer(r"([天人地])元(.)山(.)向挨星图", text))
    if len(heads) != 24:
        raise ValueError("Expected exactly 24 named mountain sections")
    cases = []
    for index, head in enumerate(heads):
        section = text[
            head.end() : (
                heads[index + 1].start() if index + 1 < len(heads) else len(text)
            )
        ]
        rows = re.findall(r"([一二三四五六七八九])运挨星，([^\n]+)", section)
        if len(rows) != 9:
            raise ValueError(f"Expected nine periods for {head[0]}")
        for period, row in rows:
            mountain = re.search(r"([一二三四五六七八九])(?:天星)?到山", row)
            facing = re.search(r"([一二三四五六七八九])(?:天星)?到向", row)
            flight = re.search(r"飞星(山向均[顺逆]|山[顺逆]向[顺逆])", row)
            if not mountain or not facing:
                raise ValueError(f"Missing literal star seeds: {row}")
            if flight:
                value = flight[1]
                orders = (
                    [value[-1]] * 2
                    if value.startswith("山向均")
                    else [value[1], value[3]]
                )
                clause = row[: flight.end()]
            else:
                m_order = re.search(r"到山，([顺逆])行", row)
                f_order = re.search(r"到向，([顺逆])行", row)
                if not m_order or not f_order:
                    raise ValueError(f"Unparsed flight orders: {row}")
                orders = [m_order[1], f_order[1]]
                clause = row[: f_order.end()]
            cases.append(
                {
                    "section": head[0],
                    "period": NUMERALS.index(period) + 1,
                    "sitting_mountain": head[2],
                    "facing_mountain": head[3],
                    "literal_clause": period + "运挨星，" + clause,
                    "mountain_seed": NUMERALS.index(mountain[1]) + 1,
                    "facing_seed": NUMERALS.index(facing[1]) + 1,
                    "mountain_flight": "forward" if orders[0] == "顺" else "reverse",
                    "facing_flight": "forward" if orders[1] == "顺" else "reverse",
                }
            )
    if len({(c["period"], c["facing_mountain"]) for c in cases}) != 216:
        raise ValueError("Duplicate or missing mountain-period pair")
    return cases


def parse_you_nian(text):
    # Inline hyperlinks split characters across text nodes. Only join
    # whitespace in the literal section; modern prose is not the oracle.
    text = re.sub(r"\s+", "", text.split("白话解读")[0])
    rows = re.findall(
        r"([乾坎艮震巽离坤兑])：([乾坎艮震巽离坤兑]{7})，([六天五祸绝延生]{7})。", text
    )
    unique = list(dict.fromkeys(rows))
    if len(unique) != 8:
        raise ValueError("Expected exactly eight literal You Nian verses")
    return [
        dict(base=base, destinations=destinations, star_codes=codes)
        for base, destinations, codes in unique
    ]


def parse_you_nian_origin(text):
    paragraph = re.search(r"画卦自下而上.*?特为捷法以括之。", text, re.S)
    if paragraph is None:
        raise ValueError("Missing literal seven-change paragraph")
    cases = []
    for numeral, chunk, star in re.findall(
        r"([一二三四五六七])变而(.*?)(?:所以为|所以為)(生气|五鬼|延年|六煞|祸害|天医|绝命)",
        paragraph[0],
        re.S,
    ):
        pairs = re.findall(r"([乾坎艮震巽离坤兑])得([乾坎艮震巽离坤兑])", chunk)
        if len(pairs) != 8:
            raise ValueError("Each change must contain eight literal trigram pairs")
        cases.extend(
            dict(
                base=base,
                target=target,
                operation_count=NUMERALS.index(numeral) + 1,
                star_name=star,
            )
            for base, target in pairs
        )
    trigrams = set("乾坎艮震巽离坤兑")
    if len(cases) != 56 or {(c["base"], c["target"]) for c in cases} != {
        (base, target) for base in trigrams for target in trigrams if base != target
    }:
        raise ValueError("Expected every distinct non-self trigram pair exactly once")
    return {"literal_paragraph": paragraph[0], "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Read previously downloaded HTML instead of network",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; existing data is never overwritten",
    )
    parser.add_argument(
        "--profile", choices=("foundation", "bazhai-depth"), default="foundation"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Output already exists; review a new snapshot before replacing a reference"
        )
    raw = {}
    urls = SOURCES if args.profile == "foundation" else BAZHAI_DEPTH_SOURCES
    for name, url in urls.items():
        if args.source_dir:
            raw[name] = (args.source_dir / (name + ".html")).read_bytes()
        else:
            with urlopen(
                Request(url, headers={"User-Agent": "FateBridge-source-audit"}),
                timeout=30,
            ) as response:
                raw[name] = response.read()
    if args.profile == "bazhai-depth":
        sources = {
            name: {
                "url": url,
                "retrieved_html_sha256": hashlib.sha256(raw[name]).hexdigest(),
            }
            for name, url in urls.items()
        }
        origin = parse_you_nian_origin(plain(raw["you_nian_origin"]))
        context = re.sub(r"\s+", "", plain(raw["fuwei_context"]).split("白话解读")[0])
        if "左辅右弼，随门而化。" not in context:
            raise ValueError("Missing literal Fu Wei context")
        args.output.mkdir(parents=True)
        reference = {
            "source": sources["you_nian_origin"],
            "source_scope": "Literal premodern transformation paragraph, excluding modern translations and event claims",
            **origin,
        }
        (args.output / "you-nian-origin.json").write_text(
            json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "source-manifest.json").write_text(
            json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            "Recorded 56 literal transformation pairs; printed element matrix requires separate manual page verification"
        )
        return
    cases = parse_shen(plain(raw["shen"]))
    verses = parse_you_nian(plain(raw["you-nian"]))
    reference = {
        "profile_id": "fengshui_classical_transcriptions_v1",
        "source_scope": "Literal numeric clauses only; uncollated web editions, no modern prose translations or outcome claims",
        "original_print_collated": False,
        "sources": {
            name: {
                "url": url,
                "retrieved_html_sha256": hashlib.sha256(raw[name]).hexdigest(),
            }
            for name, url in SOURCES.items()
        },
        "shen_cases": cases,
        "you_nian_verses": verses,
    }
    args.output.mkdir(parents=True)
    (args.output / "reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Recorded {len(cases)} Shen clauses and {len(verses)} You Nian verses; no calculated expectations"
    )


if __name__ == "__main__":
    main()
