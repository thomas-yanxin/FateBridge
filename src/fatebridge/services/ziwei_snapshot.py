"""Zi Wei birth, timing, and rules snapshot sections."""

from __future__ import annotations

from typing import Any

from fatebridge.core.local_techniques.snapshot import join_lines
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.ziwei_calendar import basis_text, placement_lunar_display
from fatebridge.core.ziwei.ziwei_rulesets import DEFAULT_ZIWEI_DAY_DIVIDE
from fatebridge.services.snapshot_builders import render_snapshot_text


def build_ziwei_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    ziwei_birth: dict[str, Any],
) -> str:
    basis = ziwei_birth["calendar_basis"]
    ming_gong = ziwei_birth["ming_gong"]
    shen_gong = ziwei_birth["shen_gong"]
    sihua = ziwei_birth["sihua"]
    palace_lines = []
    for palace in ziwei_birth.get("palaces", []) or []:
        star_text = (
            "、".join(
                (
                    f"{d['label']}({d['brightness']})"
                    if d.get("brightness")
                    else d["label"]
                )
                for d in palace["stars_detail"]
            )
            or "无"
        )
        palace_lines.append(
            (
                f"{palace.get('name', '宫位')}：{palace.get('ganzhi', '无')}；"
                f"大限：{palace.get('daxian') or '未定（缺少性别）'}；"
                f"十二长生：{palace.get('changsheng12') or '未定'}；博士十二神：{palace.get('boshi12') or '未定'}；"
                f"星曜：{star_text}"
            )
        )
    sections = [
        (
            "起盘信息",
            join_lines(
                [
                    f"排盘农历：{placement_lunar_display(basis)}",
                    f"输入钟表时间：{basis['civil_datetime']}",
                    (
                        f"参考四柱（八字日界）：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                    f"生年天干：{ziwei_birth.get('year_stem', '无')}",
                    basis_text(basis),
                    f"规则配置：{ziwei_birth['ruleset']['id']}；原典符合范围：{ziwei_birth['ruleset']['classical_conformance']}",
                    *(
                        [
                            "所选四化表：明刊卷三；本命年干原文："
                            + ziwei_birth["sihua_source_comparison"]["source_reading"],
                            "仅切换四化表，其他安星、亮度及岁序按基础配置分别核对",
                        ]
                        if ziwei_birth["ruleset"].get("sihua_source") == "naj_ming_v1"
                        else []
                    ),
                    f"闰月口径：{ziwei_birth['calendar_rules']['leap_month']}",
                    f"晚子分日口径：{ziwei_birth['calendar_rules'].get('day_divide', DEFAULT_ZIWEI_DAY_DIVIDE)}（{ziwei_birth['calendar_rules'].get('late_zi', '')}）",
                    f"亮度来源：{ziwei_birth['ruleset']['brightness_rule']}",
                    "旬空显示："
                    + "、".join(
                        ziwei_birth["void_systems"]["xun"]["displayed_star_branches"]
                    ),
                    "原文的化财、化印等象意与本命禄权科忌分别记录",
                    (
                        "明刊四化异文比较：本年干差异 "
                        f"{len(ziwei_birth['sihua_source_comparison']['differences'])} 项；"
                        "异文未套用于当前盘，不代表其他规则或全书一致"
                    ),
                    f"命主（命宫支）：{ziwei_birth['chart_masters']['life']['star']}；身主（生年支）：{ziwei_birth['chart_masters']['body']['star']}",
                    f"十二长生规则：{ziwei_birth['calendar_cycles']['changsheng_rule']}；标记仅表示传统循环名称",
                    (
                        f"命宫：{ming_gong.get('branch', '无')} / "
                        f"{ming_gong.get('ganzhi', '无')}"
                    ),
                    (
                        f"身宫：{shen_gong.get('branch', '无')} / "
                        f"{shen_gong.get('ganzhi', '无')}"
                    ),
                ]
            ),
        ),
        (
            "宫位总览",
            join_lines(
                [
                    (
                        "四化："
                        f"化禄={sihua.get('化禄', '无')}；"
                        f"化权={sihua.get('化权', '无')}；"
                        f"化科={sihua.get('化科', '无')}；"
                        f"化忌={sihua.get('化忌', '无')}"
                    ),
                    *palace_lines,
                ]
            ),
        ),
    ]
    return render_snapshot_text(sections)


def build_ziwei_horoscope_snapshot_text(
    *,
    target_seed: MetaphysicsSeed,
    horoscope: dict[str, Any],
) -> str:
    def _mutagen_line(mut: dict[str, Any]) -> str:
        return (
            f"化禄={mut.get('化禄', '无')}；化权={mut.get('化权', '无')}；"
            f"化科={mut.get('化科', '无')}；化忌={mut.get('化忌', '无')}"
        )

    sections = [
        (
            "起盘信息",
            join_lines(
                [
                    f"出生民用时刻：{horoscope['calendar_basis']['birth']['civil_datetime']}",
                    f"目标民用时刻：{horoscope['calendar_basis']['target']['civil_datetime']}",
                    f"虚岁：{horoscope.get('nominal_age', '无')}",
                    f"岁序方法：{horoscope['nominal_age_calendar']['method_id']}；参考时区：{horoscope['nominal_age_calendar']['timezone']}；原典岁首尚未认证",
                    f"目标时区：{target_seed.timezone}；目标时刻采用钟表时间",
                    "出生" + basis_text(horoscope["calendar_basis"]["birth"]),
                    "目标" + basis_text(horoscope["calendar_basis"]["target"]),
                    *(
                        [
                            f"明文童限（给定岁序{horoscope['nominal_age']}）：本命{horoscope['childhood_limit']['natal_palace_name']}，{horoscope['childhood_limit']['natal_palace_ganzhi']}",
                            "该宫本命星曜："
                            + "、".join(
                                s["label"]
                                for s in horoscope["childhood_limit"][
                                    "natal_stars_detail"
                                ]
                            ),
                            "童限与大限分列；本命四化不是童限四化，岁首与起大限前替代关系未认证",
                        ]
                        if horoscope.get("childhood_limit", {}).get("status")
                        == "computed_given_age_ordinal"
                        else []
                    ),
                    f"规则配置：{horoscope['ruleset']['id']}；原典符合范围：{horoscope['ruleset']['classical_conformance']}",
                    f"晚子分日口径：{horoscope['calendar_rules'].get('day_divide', DEFAULT_ZIWEI_DAY_DIVIDE)}（{horoscope['calendar_rules'].get('late_zi', '')}）",
                    *(
                        [
                            "所选四化表：明刊卷三；各可用层按实际天干查同表，运限复用仍为软件约定，未获原典认证"
                        ]
                        if horoscope["ruleset"].get("sihua_source") == "naj_ming_v1"
                        else []
                    ),
                ]
            ),
        )
    ]
    for s in horoscope.get("scopes", []) or []:
        if s.get("status") == "unavailable":
            sections.append(
                (
                    str(s["scope"]),
                    f"缺少明确性别，无法判定{s['scope']}顺逆；本层宫位、宫干和四化未生成。",
                )
            )
            continue
        if s.get("status") == "not_started":
            sections.append(
                (
                    str(s["scope"]),
                    f"按所选五行局起岁，尚未起正式大限（{s['first_age']}岁起）；"
                    "本层宫位、宫干和四化未生成。童限另列，不作为大限替代。",
                )
            )
            continue
        sections.append(
            (
                str(s.get("scope", "运限")),
                join_lines(
                    [
                        f"命宫活动索引所临本命宫：{s.get('natal_palace_name', s.get('palace_name', '无'))}（{s.get('palace_ganzhi', '')}）",
                        f"四化天干：{s.get('stem', '')}",
                        f"天干来源：{s.get('stem_origin', '')}",
                        f"四化：{_mutagen_line(s.get('mutagen', {}) or {})}",
                        *(
                            [
                                "本层流曜："
                                + "；".join(
                                    f"{star['star']}入{star['scope_palace_name']}（{star['branch']}，叠本命{star['natal_palace_name']}）"
                                    for star in s["flowing_stars"]
                                )
                            ]
                            if s.get("flowing_stars")
                            else []
                        ),
                        *(
                            [
                                "飞天三杀位置集合："
                                + "、".join(s["annual_three_sha"]["branches"])
                                + "（所选原文未逐名配对）"
                            ]
                            if s.get("annual_three_sha")
                            else []
                        ),
                        "本层功能宫映射（星位仍为本命）："
                        + "；".join(
                            f"{p['scope_palace_name']}={p['branch']}（本命{p['natal_palace_name']}）"
                            for p in s.get("palace_map", [])
                        ),
                    ]
                ),
            )
        )
    return render_snapshot_text(sections)


def build_ziwei_rules_snapshot_text(payload: dict[str, Any]) -> str:
    rule_catalogue = payload["rule_catalogue"]
    focused_rules = payload["focused_rules"]
    palace_sequence = "、".join(rule_catalogue["palace_sequence"])
    sihua_lines = [
        f"{stem}：" + "；".join(f"{label}={star}" for label, star in mapping.items())
        for stem, mapping in rule_catalogue["sihua_by_year_stem"].items()
    ]
    focused_sihua = focused_rules["sihua"] if focused_rules is not None else {}
    sections = [
        (
            "规则概览",
            join_lines(
                [
                    f"请求天干：{payload.get('requested_year_stem') or '全部'}",
                    f"引擎：{payload.get('engine', 'fatebridge-offline')}",
                    f"规则配置：{rule_catalogue['ruleset']['id']}；原典符合范围：{rule_catalogue['ruleset']['classical_conformance']}",
                    *(
                        [
                            "所选四化表：明刊卷三原页；仅选四化表，不认证基础配置的其他规则或历法"
                        ]
                        if rule_catalogue["ruleset"].get("sihua_source")
                        == "naj_ming_v1"
                        else []
                    ),
                ]
            ),
        ),
        ("宫位序列", palace_sequence),
        (
            "命身宫规则",
            join_lines(
                [
                    f"命宫：{rule_catalogue.get('ming_gong_method', '无')}",
                    f"身宫：{rule_catalogue.get('shen_gong_method', '无')}",
                ]
            ),
        ),
        ("四化总表", join_lines(sihua_lines) or "无"),
    ]
    if focused_sihua:
        sections.append(
            (
                "当前天干四化",
                join_lines(
                    [
                        f"天干：{focused_rules.get('year_stem', payload.get('requested_year_stem') or '无')}",
                        *[f"{label}：{star}" for label, star in focused_sihua.items()],
                    ]
                ),
            )
        )
    return render_snapshot_text(sections)
