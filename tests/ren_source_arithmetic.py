"""Independent source arithmetic, translated directly from reviewed stdlib references."""


def sike_strength(directory):
    import json
    from pathlib import Path

    folder = Path(directory)
    p = folder
    r = json.loads((p / "readings.json").read_text())
    controls = r["controls"]
    generates = r["generates"]
    rows = []
    by_case = {}
    for c in r["cases"]:
        phases = list(dict.fromkeys(c["elements"]))
        candidates = [e for e in phases if not any((controls[x] == e for x in phases))]
        anchor = candidates[0] if len(candidates) == 1 else None

        def state(e):
            if anchor is None:
                return None
            if e == anchor:
                return "旺"
            if generates[anchor] == e:
                return "相"
            if generates[e] == anchor:
                return "休"
            if controls[e] == anchor:
                return "囚"
            return "死"

        value = dict(
            id=c["id"],
            anchor_element=anchor,
            candidate_elements=candidates,
            powers={label: state(e) for label, e in zip(r["positions"], c["elements"])},
            phase_powers={e: state(e) for e in phases},
        )
        rows.append(value)
        by_case[c["id"]] = value
    comp = []
    for m in r["mentions"]:
        value = by_case[m["case"]]
        if m["target_kind"] == "element":
            actual = value["phase_powers"][m["target"]]
        elif m["target_kind"] == "position":
            actual = value["powers"][m["target"]]
        else:
            actual = [value["powers"][x] for x in m["target"]]
        if m["stated"] == "衰":
            matched = None
        elif isinstance(m["stated"], list):
            matched = sorted(actual) == sorted(m["stated"])
        else:
            matched = actual == m["stated"]
        comp.append(
            dict(
                id=m["id"],
                actual=actual,
                raw_same_state=matched,
                intended_layer=m["intended_layer"],
            )
        )
    assert len(rows) == 5 and len(comp) == 8
    assert sum((x["raw_same_state"] is True for x in comp)) == 4
    assert sum((x["raw_same_state"] is False for x in comp)) == 3
    assert sum((x["raw_same_state"] is None for x in comp)) == 1
    return dict(
        cases=rows,
        raw_mentions=comp,
        source_truth_labels_rewritten=False,
        independent_real_events=0,
    )


def daquan_cross_scan(directory):
    import json
    from pathlib import Path

    folder = Path(directory)
    p = folder
    r = json.loads((p / "readings.json").read_text())
    e = json.loads((p / "examples.json").read_text())
    b = "子丑寅卯辰巳午未申酉戌亥"
    pairs = {frozenset(x) for x in r["liuhe_pairs"]}
    rows = []
    for item in e["examples"]:
        day = item["day_ganzhi"]
        house = r["stem_houses"][day[0]]
        candidates = []
        if item["rotation_literal"] is not None:
            candidates.append(item["rotation_literal"])
        if item["stem_upper_literal"] is not None:
            candidates.append(
                (b.index(item["stem_upper_literal"]) - b.index(house)) % 12
            )
        if item["branch_upper_literal"] is not None:
            candidates.append(
                (b.index(item["branch_upper_literal"]) - b.index(day[1])) % 12
            )
        assert len(set(candidates)) <= 1, (item["id"], candidates)
        if not candidates:
            rows.append(
                dict(
                    id=item["id"],
                    day_ganzhi=day,
                    input_status="not_assessed_incomplete_context",
                    rotation=None,
                    sky_by_earth=None,
                    formula_expected=None,
                )
            )
            continue
        rotation = candidates[0]
        sky = {branch: b[(i + rotation) % 12] for i, branch in enumerate(b)}
        a, beta = (sky[house], sky[day[1]])
        crossed = (
            frozenset((a, day[1])) in pairs
            and frozenset((beta, house)) in pairs
            and (day not in r["excluded_days"])
        )
        rows.append(
            dict(
                id=item["id"],
                day_ganzhi=day,
                input_status="literal_coordinates_assessable",
                rotation=rotation,
                stem_upper=a,
                branch_upper=beta,
                sky_by_earth=sky,
                formula_expected=crossed,
            )
        )
    known = [x for x in rows if x["rotation"] is not None]
    assert len(rows) == 40 and len(known) == 36
    assert sum((x["formula_expected"] is True for x in rows)) == 26
    assert sum((x["formula_expected"] is False for x in rows)) == 10
    return dict(
        rows=rows,
        total_printed_mentions=40,
        assessable=36,
        unknown_contexts=4,
        positive_formula_contexts=26,
        negative_formula_contexts=10,
        distinct_assessable_contexts=len(
            {(x["day_ganzhi"], x["rotation"]) for x in known}
        ),
        independent_real_events=0,
    )


def tanyuan_cases(directory):
    import json
    import re
    from datetime import date, timedelta
    from pathlib import Path

    folder = Path(directory)
    p = folder
    readings = json.loads((folder / "readings.json").read_text())
    branches = "子丑寅卯辰巳午未申酉戌亥"
    stems = "甲乙丙丁戊己庚辛壬癸"
    month_names = [
        "正月",
        "二月",
        "三月",
        "四月",
        "五月",
        "六月",
        "七月",
        "八月",
        "九月",
        "十月",
        "十一月",
        "十二月",
    ]
    days = [
        "初一",
        "初二",
        "初三",
        "初四",
        "初五",
        "初六",
        "初七",
        "初八",
        "初九",
        "初十",
        "十一",
        "十二",
        "十三",
        "十四",
        "十五",
        "十六",
        "十七",
        "十八",
        "十九",
        "二十",
        "廿一",
        "廿二",
        "廿三",
        "廿四",
        "廿五",
        "廿六",
        "廿七",
        "廿八",
        "廿九",
        "三十",
    ]
    month_starts = dict(
        zip(
            [
                "小寒",
                "立春",
                "驚蟄",
                "清明",
                "立夏",
                "芒種",
                "小暑",
                "立秋",
                "白露",
                "寒露",
                "立冬",
                "大雪",
            ],
            "丑寅卯辰巳午未申酉戌亥子",
        )
    )
    general_starts = dict(
        zip(
            [
                "大寒",
                "雨水",
                "春分",
                "穀雨",
                "小滿",
                "夏至",
                "大暑",
                "處暑",
                "秋分",
                "霜降",
                "小雪",
                "冬至",
            ],
            "子亥戌酉申未午巳辰卯寅丑",
        )
    )
    lunar_year, month, leap = (1908, None, False)
    current_month, general, current_term = (None, None, None)
    lookup = {}
    for year in (1909, 1910, 1911):
        for line in (
            (folder / f"T{year}c.txt").read_text(encoding="utf-8-sig").splitlines()
        ):
            match = re.match(
                "(\\d+)年(\\d+)月(\\d+)日\\s+(\\S+)\\s+星期\\S+\\s*(\\S*)", line
            )
            if not match:
                continue
            y, m, d = map(int, match.group(1, 2, 3))
            solar = date(y, m, d)
            label, term = match.group(4, 5)
            if "月" in label:
                leap = label.startswith("閏")
                month = month_names.index(label.removeprefix("閏")) + 1
                if month == 1 and (not leap):
                    lunar_year = year
                lunar_day = 1
            else:
                lunar_day = days.index(label) + 1
            old_general, old_month = (general, current_month)
            if term:
                current_term = term
                general = general_starts.get(term, general)
                current_month = month_starts.get(term, current_month)
            if month is None:
                continue
            lookup[lunar_year, month, lunar_day, leap] = dict(
                solar_date=solar.isoformat(),
                hko_line=line.rstrip(),
                current_term_date_label=current_term,
                month_branch_candidates=sorted(
                    {current_month, old_month}
                    if term in month_starts
                    else {current_month}
                ),
                month_general_candidates=sorted(
                    {general, old_general} if term in general_starts else {general}
                ),
                term_day_underdetermined=term in general_starts or term in month_starts,
            )

    def day_pair(solar):
        cycle = (solar.toordinal() + 1721425 + 49) % 60
        return stems[cycle % 10] + branches[cycle % 12]

    rows = []
    for case in readings["cases"]:
        key = (
            case["lunar_year_cycle_hypothesis"],
            case["lunar_month"],
            case["lunar_day"],
            False,
        )
        calendar = lookup[key]
        solar = date.fromisoformat(calendar["solar_date"])
        hour_index = branches.index(case["printed_hour_branch"])
        minutes = (
            list(range(60)) + list(range(23 * 60, 24 * 60))
            if hour_index == 0
            else list(range((2 * hour_index - 1) * 60, (2 * hour_index + 1) * 60))
        )
        samples = []
        for minute in minutes:
            effective = solar + timedelta(days=minute >= 23 * 60)
            day = day_pair(effective)
            hour_stem = stems[(stems.index(day[0]) % 5 * 2 + hour_index) % 10]
            samples.append(
                dict(
                    minute_of_day=minute,
                    day_ganzhi=day,
                    hour_ganzhi=hour_stem + case["printed_hour_branch"],
                    printed_day_agrees=day == case["printed_day_ganzhi"],
                )
            )
        rows.append(
            dict(
                id=case["id"],
                lunar_date=list(key),
                **calendar,
                civil_midnight_day_ganzhi=day_pair(solar),
                printed_day_agrees_with_civil_midnight=day_pair(solar)
                == case["printed_day_ganzhi"],
                printed_general_agrees=case["printed_month_general"]
                in calendar["month_general_candidates"],
                samples=samples,
            )
        )
    assert len(rows) == 8 and sum((len(r["samples"]) for r in rows)) == 960
    return dict(
        expected_values_from_production=False,
        historical_instant_certified=False,
        whole_branch_minute_grid=True,
        continuous_interval_proof=False,
        cases=rows,
    )


def jingwei_harmony(directory):
    import json
    from itertools import combinations
    from pathlib import Path

    folder = Path(directory)
    p = folder
    inputs = json.loads((folder / "hypotheses.json").read_text())
    branches, stems = (inputs["branches"], inputs["stems"])
    houses = dict(zip(stems, inputs["houses"]))
    branch_harmony = dict(zip(branches, inputs["branch_harmony"]))
    stem_harmony = dict(zip(stems, inputs["stem_harmony"]))
    hidden_stems = dict(zip(branches, inputs["hidden_stems"]))
    models = [m["id"] for m in inputs["models"]]
    rows, days = ([], [])
    for n in range(60):
        stem, branch = (stems[n % 10], branches[n % 12])
        house, partner = (houses[stem], stem_harmony[stem])
        relations = dict(
            H1=branch_harmony[house] == branch,
            H2=houses[partner] == branch,
            H3=partner in hidden_stems[branch],
        )
        days.append(dict(day_ganzhi=stem + branch, candidates=relations))
        for rotation in range(12):
            branch_over_stem = (
                rotation == (branches.index(branch) - branches.index(house)) % 12
            )
            stem_over_branch = (
                rotation == (branches.index(house) - branches.index(branch)) % 12
            )
            hypothetical = {
                model: dict(
                    D11=branch_over_stem and relations[model],
                    D12=stem_over_branch and relations[model],
                )
                for model in models
            }
            rows.append(
                dict(
                    day_ganzhi=stem + branch,
                    rotation=rotation,
                    sky_by_earth={
                        b: branches[(i + rotation) % 12] for i, b in enumerate(branches)
                    },
                    placements=dict(
                        branch_over_stem=branch_over_stem,
                        stem_over_branch=stem_over_branch,
                    ),
                    hypothetical=hypothetical,
                    adjudicated_source_truth=dict(D11=None, D12=None),
                    selected_production_model=None,
                )
            )
    result = dict(
        diagnostic_only=True,
        production_imported=False,
        new_adjudicated_rules=0,
        new_independent_historical_events=0,
        new_empirical_events=0,
        days=days,
        contexts=rows,
        candidate_true_counts={
            m: {
                rule: sum((r["hypothetical"][m][rule] for r in rows))
                for rule in ["D11", "D12"]
            }
            for m in models
        },
        disagreements=[
            dict(
                models=[a, b],
                day_ganzhi=[
                    d["day_ganzhi"]
                    for d in days
                    if d["candidates"][a] != d["candidates"][b]
                ],
                contexts=[
                    dict(day_ganzhi=r["day_ganzhi"], rotation=r["rotation"])
                    for r in rows
                    if r["hypothetical"][a] != r["hypothetical"][b]
                ],
            )
            for a, b in combinations(models, 2)
        ],
    )
    return result


def day_placements(directory):
    import json
    from pathlib import Path

    folder = Path(directory)
    p = folder
    reading = json.loads((folder / "readings.json").read_text())
    branches = "子丑寅卯辰巳午未申酉戌亥"
    stems = "甲乙丙丁戊己庚辛壬癸"
    houses = "寅辰巳未巳未申戌亥丑"
    branch_phases = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
    rows = []
    for day_index in range(60):
        stem_index, branch_index = (day_index % 10, day_index % 12)
        day = stems[stem_index] + branches[branch_index]
        stem_phase, branch_phase = (stem_index // 2, branch_phases[branch_index])
        house_index = branches.index(houses[stem_index])
        relations = dict(
            branch_generates_stem=(branch_phase + 1) % 5 == stem_phase,
            stem_generates_branch=(stem_phase + 1) % 5 == branch_phase,
            branch_controls_stem=(branch_phase + 2) % 5 == stem_phase,
            stem_controls_branch=(stem_phase + 2) % 5 == branch_phase,
            same_element=branch_phase == stem_phase,
        )
        for rotation in range(12):
            placements = dict(
                stem_over_branch=rotation == (house_index - branch_index) % 12,
                branch_over_stem=rotation == (branch_index - house_index) % 12,
            )
            evaluations = [
                dict(
                    id=c["id"],
                    matched=(
                        placements[c["placement"]] and relations[c["relation"]]
                        if c["definition_adjudicated"]
                        else None
                    ),
                )
                for c in reading["clauses"]
            ]
            rows.append(
                dict(
                    day_ganzhi=day,
                    rotation=rotation,
                    sky_by_earth={
                        b: branches[(i + rotation) % 12] for i, b in enumerate(branches)
                    },
                    placements=placements,
                    element_relations=relations,
                    evaluations=evaluations,
                    matched_ids=[r["id"] for r in evaluations if r["matched"] is True],
                    unresolved_ids=["D11", "D12"],
                )
            )
    assert len(rows) == 720
    result = dict(
        source="Independent literal arithmetic enumeration, not historical cases or observations",
        source_sha256=reading["source_sha256"],
        production_imported=False,
        production_calculations_performed=False,
        contexts=rows,
    )
    return result


def cross_harmony(directory):
    import json
    from pathlib import Path

    folder = Path(directory)
    p = folder
    reading = json.loads((folder / "readings.json").read_text())
    branches = "子丑寅卯辰巳午未申酉戌亥"
    stems = "甲乙丙丁戊己庚辛壬癸"
    pairs = {frozenset(pair) for pair in reading["liuhe_pairs"]}
    rows = []
    for i in range(60):
        day = stems[i % 10] + branches[i % 12]
        house = reading["stem_houses"][day[0]]
        for rotation in range(12):
            sky = {b: branches[(j + rotation) % 12] for j, b in enumerate(branches)}
            upper_stem, upper_branch = (sky[house], sky[day[1]])
            first = frozenset((upper_stem, day[1])) in pairs
            second = frozenset((upper_branch, house)) in pairs
            distinct = house != day[1]
            rows.append(
                dict(
                    day_ganzhi=day,
                    rotation=rotation,
                    day_stem_house=house,
                    day_branch=day[1],
                    stem_upper=upper_stem,
                    branch_upper=upper_branch,
                    sky_by_earth=sky,
                    distinct_anchors=distinct,
                    stem_upper_with_day_branch=first,
                    branch_upper_with_stem_house=second,
                    both_cross_pairs=first and second,
                    matched=distinct and first and second,
                    upper_pair_liuhe=frozenset((upper_stem, upper_branch)) in pairs,
                )
            )
    excluded = [
        stems[i % 10] + branches[i % 12]
        for i in range(60)
        if reading["stem_houses"][stems[i % 10]] == branches[i % 12]
    ]
    assert set(excluded) == set(reading["excluded_days"])
    assert len(rows) == 720
    assert sum((r["both_cross_pairs"] for r in rows)) == 60
    assert sum((r["matched"] for r in rows)) == 55
    assert all(
        (
            sum(
                (
                    r["matched"]
                    for r in rows
                    if r["day_ganzhi"] == stems[i % 10] + branches[i % 12]
                )
            )
            == (0 if stems[i % 10] + branches[i % 12] in excluded else 1)
            for i in range(60)
        )
    )
    return dict(
        expected_values_from_production=False,
        contexts=rows,
        total_contexts=720,
        mathematical_cross_pairs_true=60,
        named_structure_matched=55,
        shared_anchor_excluded_days=excluded,
        independent_historical_or_empirical_events=0,
    )


def polarity(readings):
    from collections import Counter

    stems, branches = (readings["stems"], readings["branches"])
    positions = readings["positions"]
    truth = {
        mask: (pattern, use) for mask, pattern, use in readings["formal_truth_table"]
    }
    rows, masks, uses = ([], Counter(), Counter())
    for ordinal in range(60):
        day = stems[ordinal % 10] + branches[ordinal % 12]
        start_stem = next(
            (s for group, s in readings["wuzi_groups"] if day[0] in group)
        )
        start_index = stems.index(start_stem)
        xun = ordinal // 10 * 10
        empties = {branches[(xun + 10) % 12], branches[(xun + 11) % 12]}
        empty_phase = {0: "水", 20: "金", 30: "水", 50: "金"}.get(xun)
        guiren = next((r for r in readings["guiren"] if r["stem"] == day[0]))
        for diurnal in (False, True):
            start = guiren["day" if diurnal else "night"]
            step = -1 if start in readings["reverse_start_branches"] else 1
            for ground_index, ground in enumerate(branches):
                offset = (ground_index - branches.index(start)) * step % 12
                name = readings["god_sequence"][offset]
                intrinsic = readings["inherent"][name]
                ren = stems[(start_index + ground_index) % 10]
                for general_index, general in enumerate(branches):
                    jiang = branches[(general_index + ground_index) % 12]
                    contents = [ren, intrinsic[1], jiang, ground]
                    mask = readings["stem_polarity"][ren] + "".join(
                        (readings["branch_polarity"][v] for v in contents[1:])
                    )
                    phases = [readings["stem_elements"][ren]] + [
                        readings["branch_elements"][v] for v in contents[1:]
                    ]
                    pattern, use = truth[mask]
                    selected = positions.index(use)
                    controllers = [
                        p
                        for p, phase in zip(positions, phases)
                        if readings["controls"][phase] == phases[selected]
                    ]
                    xun_flags = [False] + [v in empties for v in contents[1:]]
                    si_da_flags = [e == empty_phase for e in phases]
                    month_flags = [False] + [v == "申" for v in contents[1:]]
                    rows.append(
                        dict(
                            day=day,
                            is_diurnal=diurnal,
                            ground=ground,
                            general=general,
                            contents=contents,
                            god=name,
                            intrinsic_ganzhi=intrinsic,
                            dun_stems=[
                                None,
                                stems[
                                    (start_index + branches.index(intrinsic[1])) % 10
                                ],
                                stems[(start_index + branches.index(jiang)) % 10],
                                None,
                            ],
                            mask=mask,
                            pattern=pattern,
                            use=use,
                            xun_kong=xun_flags,
                            si_da_kong=si_da_flags,
                            month_break=month_flags,
                            controlled_by=controllers,
                        )
                    )
                    masks[mask] += 1
                    uses[use] += 1
    return dict(
        cases=rows,
        mask_counts=dict(sorted(masks.items())),
        use_counts=dict(sorted(uses.items())),
        unreachable_masks=sorted(set(truth) - set(masks)),
        scope=readings["scope"],
    )
