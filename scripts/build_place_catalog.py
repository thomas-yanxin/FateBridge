"""Import pinned local gazetteer extracts; audit the shipped catalog offline.

See docs/place-catalog.md for download URLs, licenses, selection and precision.
No network access is performed by this script.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pytz import timezone as lookup_timezone

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src/fatebridge/data/places"
RELEASE = "2025.251231.260403"
FILES = (
    "ok_data_level3.csv",
    "ok_geo.csv",
    "cities15000.zip",
    "countryInfo.txt",
    "admin1CodesASCII.txt",
    "TW.zip",
    "ok_data_level3-4.csv.7z",
    "ok_geo.csv.7z",
)
COUNTRY_ZH = dict(
    CN="中国",
    US="美国",
    GB="英国",
    CA="加拿大",
    AU="澳大利亚",
    NZ="新西兰",
    FR="法国",
    DE="德国",
    IT="意大利",
    ES="西班牙",
    PT="葡萄牙",
    JP="日本",
    KR="韩国",
    KP="朝鲜",
    RU="俄罗斯",
    IN="印度",
    BR="巴西",
    AR="阿根廷",
    ZA="南非",
    EG="埃及",
    KE="肯尼亚",
    NG="尼日利亚",
    TH="泰国",
    VN="越南",
    SG="新加坡",
    MY="马来西亚",
    ID="印度尼西亚",
    PH="菲律宾",
    PK="巴基斯坦",
    BD="孟加拉国",
    LK="斯里兰卡",
    NP="尼泊尔",
    MM="缅甸",
    KH="柬埔寨",
    LA="老挝",
    MN="蒙古",
    IL="以色列",
    TR="土耳其",
    IR="伊朗",
    IQ="伊拉克",
    AE="阿联酋",
    SA="沙特阿拉伯",
    QA="卡塔尔",
    KW="科威特",
    OM="阿曼",
    CH="瑞士",
    AT="奥地利",
    NL="荷兰",
    BE="比利时",
    IE="爱尔兰",
    DK="丹麦",
    SE="瑞典",
    NO="挪威",
    FI="芬兰",
    IS="冰岛",
    PL="波兰",
    CZ="捷克",
    HU="匈牙利",
    GR="希腊",
    UA="乌克兰",
    RO="罗马尼亚",
    MX="墨西哥",
    CL="智利",
    PE="秘鲁",
    CO="哥伦比亚",
    VE="委内瑞拉",
    EC="厄瓜多尔",
    UY="乌拉圭",
    BO="玻利维亚",
    CU="古巴",
    PA="巴拿马",
    MA="摩洛哥",
    DZ="阿尔及利亚",
    TN="突尼斯",
    ET="埃塞俄比亚",
    GH="加纳",
    TZ="坦桑尼亚",
    UG="乌干达",
    SN="塞内加尔",
    ZW="津巴布韦",
    MU="毛里求斯",
    FJ="斐济",
    PG="巴布亚新几内亚",
    WS="萨摩亚",
    TO="汤加",
    HK="香港",
    MO="澳门",
    TW="台湾",
)
PREFERRED = {
    "北京": "CN:110000",
    "上海": "CN:310000",
    "天津": "CN:120000",
    "重庆": "CN:500000",
    "苏州": "CN:320500",
    "福州": "CN:350100",
    "纽约": "GN:5128581",
    "伦敦": "GN:2643743",
    "东京": "GN:1850147",
    "悉尼": "GN:2147714",
}


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gcj02_to_wgs84(lon: float, lat: float) -> tuple[float, float]:
    """Iteratively invert the public GCJ approximation, not a survey transform.

    The residual below describes numerical convergence only. It is NOT an
    estimate of positional accuracy in metres. Source points are city centres.
    """
    if not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271):
        return lon, lat

    def offset(xlon: float, ylat: float) -> tuple[float, float]:
        x, y = xlon - 105, ylat - 35
        dlat = (
            -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        )
        dlon = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        wave = (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
        dlat += (
            wave + (20 * math.sin(y * math.pi) + 40 * math.sin(y * math.pi / 3)) * 2 / 3
        )
        dlat += (
            (160 * math.sin(y * math.pi / 12) + 320 * math.sin(y * math.pi / 30))
            * 2
            / 3
        )
        dlon += (
            wave + (20 * math.sin(x * math.pi) + 40 * math.sin(x * math.pi / 3)) * 2 / 3
        )
        dlon += (
            (150 * math.sin(x * math.pi / 12) + 300 * math.sin(x * math.pi / 30))
            * 2
            / 3
        )
        rad = math.radians(ylat)
        magic = 1 - 0.00669342162296594323 * math.sin(rad) ** 2
        dlat = (
            dlat
            * 180
            / ((6378245 * (1 - 0.00669342162296594323)) / (magic**1.5) * math.pi)
        )
        dlon = dlon * 180 / (6378245 / math.sqrt(magic) * math.cos(rad) * math.pi)
        return dlon, dlat

    guess_lon, guess_lat = lon, lat
    for _ in range(10):
        dx, dy = offset(guess_lon, guess_lat)
        ex, ey = guess_lon + dx - lon, guess_lat + dy - lat
        guess_lon -= ex
        guess_lat -= ey
        if max(abs(ex), abs(ey)) < 1e-9:
            break
    return round(guess_lon, 6), round(guess_lat, 6)


def geonames(path: Path, member: str) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        return [r.split("\t") for r in archive.read(member).decode().splitlines()]


def build(source: Path) -> None:
    from opencc import OpenCC  # Development-only dependency; never used at runtime.

    simplified, traditional = OpenCC("t2s"), OpenCC("s2t")

    def variants(values: list[str]) -> list[str]:
        return sorted(
            {
                v
                for x in values
                if x
                for v in (x, simplified.convert(x), traditional.convert(x))
            }
        )

    legacy = json.loads(
        (ROOT / "scripts/data/place_alias_overrides.json").read_text(encoding="utf-8")
    )
    legacy_by_name = {r["canonical_name"]: r for r in legacy}
    csv.field_size_limit(10_000_000)
    with (source / "ok_data_level3.csv").open(encoding="utf-8-sig") as handle:
        names = list(csv.DictReader(handle))
    with (source / "ok_geo.csv").open(encoding="utf-8-sig") as handle:
        points = {r["id"]: r for r in csv.DictReader(handle)}

    china: dict[str, dict[str, Any]] = {}
    current_names = {r["ext_name"] for r in names}
    # Deduplicate the artificial levels used by cascading address selectors.
    # ext_id is the original code; id may be a synthetic repeated child.
    for row in names:
        prefix = int(row["id"][:2])
        if prefix > 82 or prefix == 71:
            continue
        code = row["ext_id"][:6]
        if code in {"110100", "120100", "310100", "500100", "500200"}:
            continue
        key = f"CN:{code}"
        if key in china:
            continue
        if code.endswith("0000"):
            level = "municipality" if prefix in {11, 12, 31, 50} else "province"
            if prefix in {81, 82}:
                level = "special_region"
            parent = None
        elif code.endswith("00"):
            level, parent = "city", f"CN:{code[:2]}0000"
        else:
            level = "county"
            # Direct-administered cities have no real prefecture in this table.
            pcode = next(r["ext_id"][:6] for r in names if r["id"] == row["pid"])
            parent = f"CN:{pcode}" if pcode != code else f"CN:{code[:2]}0000"
            if pcode in {"110100", "120100", "310100", "500100", "500200"}:
                parent = f"CN:{code[:2]}0000"
        full, short = row["ext_name"], row["name"]
        if full.endswith("市"):
            short = full[:-1]
        canonical = short if level != "county" or full.endswith("市") else full
        old = legacy_by_name.get(short) or legacy_by_name.get(full)
        aliases = [full, short, row["pinyin"], row["pinyin"].replace(" ", "")]
        if old and old["level"] == level:
            canonical = old["canonical_name"]
            # A prefecture and a same-named county are separate records.
            aliases += [
                a
                for a in old["aliases"]
                if a in {full, short} or a not in current_names
            ]
        raw = points[row["id"]]["geo"]
        if raw == "EMPTY":
            raise ValueError(f"Missing Chinese coordinate: {key} {full}")
        lon, lat = map(float, raw.split())
        wlon, wlat = gcj02_to_wgs84(lon, lat)
        china[key] = dict(
            id=key,
            canonical_name=canonical,
            full_name=full,
            parent=parent,
            aliases=variants(aliases),
            level=level,
            country="CN",
            continent="AS",
            longitude=wlon,
            latitude=wlat,
            timezone=(
                "Asia/Hong_Kong"
                if prefix == 81
                else (
                    "Asia/Macau"
                    if prefix == 82
                    else "Asia/Taipei" if code == "350527" else "Asia/Shanghai"
                )
            ),
            source="areacity",
            source_id=row["id"],
            source_coordinates=[lon, lat],
            coordinate_system="WGS84_approx",
        )
    # Restore direct-administered counties to a real parent (not their synthetic
    # child); ordinary prefecture parents must already exist.
    for r in china.values():
        if r["parent"] not in china and r["parent"] is not None:
            r["parent"] = f"CN:{r['id'][3:5]}0000"

    tw = geonames(source / "TW.zip", "TW.txt")
    tw_admin = [r for r in tw if r[7] in {"ADM2", "ADM3"}]
    taipei_point = next(r for r in tw if r[0] == "1668341")
    province = dict(
        id="CN:710000",
        canonical_name="台湾",
        full_name="台湾省",
        parent=None,
        aliases=variants(["台湾", "台湾省", "Taiwan"]),
        level="province",
        country="CN",
        continent="AS",
        longitude=float(taipei_point[5]),
        latitude=float(taipei_point[4]),
        timezone="Asia/Taipei",
        source="geonames",
        source_id="1668341",
        coordinate_system="WGS84",
    )
    china[province["id"]] = province
    tw_parents = {r[11]: f"GN:{r[0]}" for r in tw_admin if r[7] == "ADM2"}
    for row in tw_admin:
        chinese = [
            simplified.convert(a).replace("臺", "台")
            for a in row[3].split(",")
            if re.fullmatch(r"[\u4e00-\u9fff]+", a)
        ]
        suffixes = ("县", "市") if row[7] == "ADM2" else ("区", "镇", "乡", "市")
        full = next((a for a in chinese if a.endswith(suffixes)), None)
        if full is None:
            raise ValueError(f"Missing Taiwan administrative name: {row[:4]}")
        short = full[:-1]
        city = row[7] == "ADM2" and full.endswith("市")
        canonical = short if city else full
        parent = "CN:710000" if row[7] == "ADM2" else tw_parents[row[11]]
        point = row
        # Use the populated-place centre for a city, not its administrative area
        # centroid. For counties/townships, retain the published admin point.
        if full.endswith("市"):
            seats = [
                r
                for r in tw
                if r[6] == "P"
                and r[11] == row[11]
                and (row[7] == "ADM2" or r[12] == row[12])
                and full in [simplified.convert(a) for a in r[3].split(",")]
            ]
            if seats:
                point = max(seats, key=lambda r: int(r[14]))
        # Historical names such as 臺灣省 for New Taipei would corrupt parent
        # matching. Only use current Chinese administrative names here.
        aliases = [full, *([short] if len(short) > 1 else []), row[1], row[2]]
        if canonical in legacy_by_name:
            aliases += legacy_by_name[canonical]["aliases"]
        china[f"GN:{row[0]}"] = dict(
            id=f"GN:{row[0]}",
            canonical_name=canonical,
            full_name=full,
            parent=parent,
            aliases=variants(aliases),
            level="city" if row[7] == "ADM2" else "county",
            country="CN",
            continent="AS",
            longitude=float(point[5]),
            latitude=float(point[4]),
            timezone="Asia/Taipei",
            source="geonames",
            source_id=point[0],
            coordinate_system="WGS84",
        )

    countries = {}
    for line in (source / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            r = line.split("\t")
            countries[r[0]] = dict(
                name=r[4],
                continent=r[8],
                aliases=variants([r[0], r[1], r[4], COUNTRY_ZH.get(r[0], "")]),
            )
    countries["US"]["aliases"] += ["USA", "United States of America", "美國"]
    countries["GB"]["aliases"] += ["UK", "Great Britain", "英國"]
    countries["CN"]["aliases"] += ["中国", "中國", "中华人民共和国", "PRC"]
    countries["AU"]["aliases"] += ["澳洲"]
    admins = {
        r[0]: [r[1], r[2]]
        for line in (source / "admin1CodesASCII.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if (r := line.split("\t")) and len(r) == 4
    }
    rows = [
        r
        for r in geonames(source / "cities15000.zip", "cities15000.txt")
        if r[8] not in {"CN", "TW", "HK", "MO"}
        and r[8] in countries
        and countries[r[8]]["continent"] != "AN"
        and r[7] in {"PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPL"}
        and r[17]
    ]
    by_country: dict[str, list[list[str]]] = defaultdict(list)
    for r in rows:
        by_country[r[8]].append(r)
    selected = {r[0] for r in rows if int(r[14]) >= 100_000 or r[7] in {"PPLC", "PPLA"}}
    for group in by_country.values():
        selected.update(r[0] for r in sorted(group, key=lambda r: -int(r[14]))[:3])
    oceania = [r for r in rows if countries[r[8]]["continent"] == "OC"]
    selected.update(r[0] for r in sorted(oceania, key=lambda r: -int(r[14]))[:50])
    world = []
    for r in rows:
        if r[0] not in selected:
            continue
        aliases = [
            r[1],
            r[2],
            *[a for a in r[3].split(",") if re.fullmatch(r"[\u4e00-\u9fff]+", a)],
        ]
        canonical = r[1]
        key = f"GN:{r[0]}"
        for name, preferred in PREFERRED.items():
            if key == preferred and name in legacy_by_name:
                canonical = name
                aliases += legacy_by_name[name]["aliases"]
        world.append(
            dict(
                id=key,
                canonical_name=canonical,
                full_name=r[1],
                parent=None,
                aliases=variants(aliases),
                level="city",
                country=r[8],
                continent=countries[r[8]]["continent"],
                longitude=float(r[5]),
                latitude=float(r[4]),
                timezone=r[17],
                source="geonames",
                source_id=r[0],
                coordinate_system="WGS84",
                admin1_aliases=variants([r[10], *admins.get(f"{r[8]}.{r[10]}", [])]),
                population=int(r[14]),
                feature_code=r[7],
                source_modified=r[18],
            )
        )
    DEST.mkdir(parents=True, exist_ok=True)
    preferred_aliases = dict(PREFERRED)
    for old in legacy:
        if old["level"] == "province":
            continue
        candidates = [
            r
            for r in [*china.values(), *world]
            if r["canonical_name"] == old["canonical_name"]
            and r["level"] == old["level"]
        ]
        if len(candidates) == 1:
            preferred_aliases[old["canonical_name"]] = candidates[0]["id"]
    for filename, records in (
        ("china.json", list(china.values())),
        ("world.json", world),
    ):
        (DEST / filename).write_text(
            "[\n"
            + ",\n".join(dump(r) for r in sorted(records, key=lambda r: r["id"]))
            + "\n]\n",
            encoding="utf-8",
            newline="\n",
        )
    (DEST / "countries.json").write_text(
        json.dumps(countries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    mainland = [
        r
        for r in china.values()
        if r["source"] == "areacity" and int(r["id"][3:5]) < 71
    ]
    manifest = dict(
        version=1,
        retrieved_on="2026-10-22",
        areacity_release=RELEASE,
        sources={
            f: dict(
                sha256=digest(source / f),
                url=(
                    f"https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov/releases/download/{RELEASE}/{f}"
                    if f.endswith(".7z")
                    else (
                        f"https://download.geonames.org/export/dump/{f}"
                        if not f.endswith(".csv")
                        else f"extracted from AreaCity {RELEASE}"
                    )
                ),
                license="MIT" if f.startswith("ok_") else "CC-BY-4.0",
            )
            for f in FILES
        },
        files={
            f: digest(DEST / f) for f in ("china.json", "world.json", "countries.json")
        },
        counts=dict(
            china=len(china),
            mainland=dict(Counter(r["level"] for r in mainland)),
            mainland_county_cities=sum(
                r["level"] == "county" and r["full_name"].endswith("市")
                for r in mainland
            ),
            mainland_prefecture_cities=sum(
                r["level"] == "city" and r["full_name"].endswith("市") for r in mainland
            ),
            taiwan_admin_units=len(tw_admin),
            world=len(world),
            world_by_continent=dict(
                sorted(Counter(r["continent"] for r in world).items())
            ),
        ),
        mainland_county_city_codes=sorted(
            r["id"][3:]
            for r in mainland
            if r["level"] == "county" and r["full_name"].endswith("市")
        ),
        preferred_aliases=preferred_aliases,
        known_gaps=[
            "AreaCity release excludes newly established 和康县 and 和安县; no coordinates invented."
        ],
    )
    (DEST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    audit()


def audit() -> None:
    manifest = json.loads((DEST / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["files"].items():
        if digest(DEST / filename) != expected:
            raise ValueError(f"Catalog checksum mismatch: {filename}")
    records = json.loads(
        (DEST / "china.json").read_text(encoding="utf-8")
    ) + json.loads((DEST / "world.json").read_text(encoding="utf-8"))
    ids = {r["id"] for r in records}
    if len(ids) != len(records):
        raise ValueError("Duplicate place IDs")
    for r in records:
        if not (-180 <= r["longitude"] <= 180 and -90 <= r["latitude"] <= 90):
            raise ValueError(f"Invalid coordinate: {r['id']}")
        lookup_timezone(r["timezone"])
        if r["parent"] is not None and r["parent"] not in ids:
            raise ValueError(f"Missing parent: {r['id']}")
        if not r["aliases"]:
            raise ValueError(f"Missing aliases: {r['id']}")
        if r["source"] == "areacity":
            expected_lon, expected_lat = gcj02_to_wgs84(*r["source_coordinates"])
            if (r["longitude"], r["latitude"]) != (expected_lon, expected_lat):
                raise ValueError(f"Coordinate conversion drift: {r['id']}")
    cn = [r for r in records if r["source"] == "areacity" and int(r["id"][3:5]) < 71]
    codes = sorted(
        r["id"][3:]
        for r in cn
        if r["level"] == "county" and r["full_name"].endswith("市")
    )
    if codes != manifest["mainland_county_city_codes"] or len(codes) != 397:
        raise ValueError("Incomplete mainland county-city coverage")
    if sum(r["level"] == "city" for r in cn) != 333:
        raise ValueError("Incomplete mainland prefecture coverage")
    by_id = {r["id"]: r for r in records}
    for r in records:
        seen = {r["id"]}
        parent = r["parent"]
        while parent is not None:
            if parent in seen:
                raise ValueError(f"Cyclic hierarchy: {r['id']}")
            seen.add(parent)
            parent = by_id[parent]["parent"]
    world = [r for r in records if r["country"] != "CN"]
    actual_counts = dict(
        china=len(records) - len(world),
        mainland=dict(Counter(r["level"] for r in cn)),
        mainland_county_cities=len(codes),
        mainland_prefecture_cities=sum(
            r["level"] == "city" and r["full_name"].endswith("市") for r in cn
        ),
        taiwan_admin_units=sum(
            r["source"] == "geonames" and r["id"] != "CN:710000"
            for r in records
            if r["country"] == "CN"
        ),
        world=len(world),
        world_by_continent=dict(sorted(Counter(r["continent"] for r in world).items())),
    )
    if actual_counts != manifest["counts"]:
        raise ValueError("Catalog count manifest is stale")
    counts = Counter(
        "AM" if r["continent"] in {"NA", "SA"} else r["continent"] for r in world
    )
    if (
        len(world) < 500
        or set(counts) != {"AS", "EU", "AF", "AM", "OC"}
        or min(counts.values()) < 30
    ):
        raise ValueError("Insufficient five-continent coverage")
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing the source extracts and archives",
    )
    parser.add_argument(
        "--check", action="store_true", help="Audit packaged data offline"
    )
    args = parser.parse_args()
    if args.check:
        audit()
    elif args.source_dir:
        build(args.source_dir)
    else:
        parser.error("Specify --source-dir or --check")


if __name__ == "__main__":
    main()
