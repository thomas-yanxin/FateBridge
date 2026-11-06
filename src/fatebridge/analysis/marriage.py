"""
婚姻分析模块

基于八字命理的婚姻分析功能，综合以下经典技法：
- 曲炜《八字婚姻断法》：配偶星、配偶宫、婚期推断
- 盲派婚姻技法：日支看配偶、财官看婚姻
- 神煞辅助：红鸾、天喜、桃花、孤辰寡宿

核心分析维度：
1. 配偶星定位与特征
2. 配偶宫（日支）分析
3. 婚姻质量评估
4. 婚期推断
5. 婚姻风险提示
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..utils.data import (
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    TenGod,
    get_ten_god,
    iter_pillar_gods,
    normalize_gender,
)

# 地支所主性格特征
BRANCH_PERSONALITY = {
    "子": "聪明机敏、善变灵活",
    "丑": "稳重踏实、内敛含蓄",
    "寅": "积极进取、有领导力",
    "卯": "温文尔雅、心思细腻",
    "辰": "胸怀大志、包容性强",
    "巳": "热情聪慧、洞察力强",
    "午": "热情奔放、直率坦荡",
    "未": "温和善良、重视家庭",
    "申": "果断干练、善于交际",
    "酉": "精致讲究、追求完美",
    "戌": "忠诚可靠、正义感强",
    "亥": "善良包容、富有同情心",
}

# 地支五行主外貌特征
BRANCH_APPEARANCE = {
    "木": "身材修长、面容清秀",
    "火": "面色红润、五官鲜明",
    "土": "体态敦厚、面方额阔",
    "金": "骨架分明、轮廓清晰",
    "水": "面色偏黑或偏白、灵动有神",
}

# 地支六合主感情和谐
SIX_HARMONY = {
    frozenset(("子", "丑")): "土",
    frozenset(("寅", "亥")): "木",
    frozenset(("卯", "戌")): "火",
    frozenset(("辰", "酉")): "金",
    frozenset(("巳", "申")): "水",
    frozenset(("午", "未")): "土",
}

# 地支六冲主感情冲突
SIX_CLASH = [
    ("子", "午"),
    ("丑", "未"),
    ("寅", "申"),
    ("卯", "酉"),
    ("辰", "戌"),
    ("巳", "亥"),
]


class MarriageAnalysis:
    """婚姻分析工具类"""

    @staticmethod
    def analyze_marriage(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合婚姻分析。

        Args:
            pillars: 四柱 {"year": (stem, branch), "month": (...), "day": (...), "hour": (...)}
            gender: 性别 "male"/"female"/"男"/"女"
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            婚姻分析结果字典
        """
        day_stem = pillars["day"][0]
        day_branch = pillars["day"][1]
        normalized_gender = normalize_gender(gender)
        if normalized_gender not in ("male", "female"):
            return {
                "gender_basis": "unselected_gender_alternatives",
                "spouse_star": {
                    "spouse_star_type": "未选定传统配偶星口径",
                    "spouse_star_strength": "未评定",
                    "alternatives": {
                        "male": MarriageAnalysis._analyze_spouse_star(
                            pillars, day_stem, True
                        ),
                        "female": MarriageAnalysis._analyze_spouse_star(
                            pillars, day_stem, False
                        ),
                    },
                },
                "spouse_palace": MarriageAnalysis._analyze_spouse_palace(
                    pillars, day_branch, day_stem
                ),
                "marriage_quality": {
                    "score": None,
                    "quality_level": "未评定",
                    "notes": ["性别未选定，不默认套用女命规则或合并两套分数。"],
                },
                "marriage_shensha": MarriageAnalysis._check_marriage_shensha(pillars),
                "marriage_timing": {
                    "timing_signals": [],
                    "marriage_tendency": "未评定",
                    "tendency_notes": ["保留独立日支关系；性别相关婚期口径不作选择。"],
                },
                "risk_factors": [],
                "suggestions": [
                    "先对照实际相处、沟通与双方安排；个人单盘不能判断关系成败。"
                ],
            }
        is_male = normalized_gender == "male"

        spouse_star = MarriageAnalysis._analyze_spouse_star(pillars, day_stem, is_male)

        spouse_palace = MarriageAnalysis._analyze_spouse_palace(
            pillars, day_branch, day_stem
        )

        marriage_quality = MarriageAnalysis._assess_marriage_quality(
            pillars, day_stem, day_branch, is_male
        )

        marriage_shensha = MarriageAnalysis._check_marriage_shensha(pillars)

        marriage_timing = MarriageAnalysis._predict_marriage_timing(
            pillars, day_stem, day_branch, is_male, dayun_pillar, liunian_pillar
        )

        risk_factors = MarriageAnalysis._identify_risk_factors(
            pillars, day_stem, day_branch, is_male
        )

        suggestions = MarriageAnalysis._generate_suggestions(
            spouse_star,
            spouse_palace,
            marriage_quality,
            marriage_shensha,
            risk_factors,
            is_male,
        )

        return {
            "gender_basis": normalized_gender,
            "interpretation_scope": "命主单盘的传统对应；分数为固定规则指数，不是婚姻质量测量或成败概率。",
            "spouse_star": spouse_star,
            "spouse_palace": spouse_palace,
            "marriage_quality": marriage_quality,
            "marriage_shensha": marriage_shensha,
            "marriage_timing": marriage_timing,
            "risk_factors": risk_factors,
            "suggestions": suggestions,
        }

    @staticmethod
    def _analyze_spouse_star(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        is_male: bool,
    ) -> Dict[str, Any]:
        """
        分析配偶星。
        男命以财星为配偶星（正财为妻），女命以官星为配偶星（正官为夫）。
        """
        # 确定配偶星十神
        if is_male:
            spouse_god = TenGod.POSITIVE_WEALTH
            spouse_god_alt = TenGod.PARTIAL_WEALTH
            spouse_label = "财星"
            spouse_label_alt = "偏财"
        else:
            spouse_god = TenGod.POSITIVE_OFFICER
            spouse_god_alt = TenGod.SEVEN_KILLER
            spouse_label = "官星"
            spouse_label_alt = "七杀"

        # 日干自身不计，但配偶宫中的藏干也是配偶星的真实位置。
        spouse_star_positions: List[Dict[str, Any]] = []
        for e in iter_pillar_gods(pillars, day_stem):
            if e.ten_god != spouse_god and e.ten_god != spouse_god_alt:
                continue
            is_stem = e.location == "天干"
            spouse_star_positions.append(
                {
                    "position": e.pillar if is_stem else f"{e.pillar}_hidden",
                    "stem": e.char,
                    "branch": e.branch,
                    "ten_god": e.ten_god.value,
                    "is_primary": e.ten_god == spouse_god,
                }
            )

        # 配偶星旺衰判断
        spouse_star_strength = "未现"
        if spouse_star_positions:
            primary_count = sum(1 for s in spouse_star_positions if s["is_primary"])
            if primary_count >= 2:
                spouse_star_strength = "偏旺"
            elif primary_count == 1:
                spouse_star_strength = "适中"
            else:
                spouse_star_strength = "偏弱（只见偏星）"

        # 配偶星五行特征
        spouse_element = None
        if is_male:
            day_element = STEM_ELEMENTS[day_stem][0]
            spouse_element = DESTRUCTION_CYCLE.get(day_element)
        else:
            day_element = STEM_ELEMENTS[day_stem][0]
            for elem, destroyed in DESTRUCTION_CYCLE.items():
                if destroyed == day_element:
                    spouse_element = elem
                    break

        appearance = BRANCH_APPEARANCE.get(
            spouse_element.value if spouse_element else "", "需结合全局判断"
        )

        return {
            "spouse_star_type": spouse_label,
            "spouse_star_alt": spouse_label_alt,
            "spouse_star_positions": spouse_star_positions,
            "spouse_star_strength": spouse_star_strength,
            "counting_scope": "含日支藏干；此字段为出现次数分类，不是根气、得令及制化后的旺衰。",
            "spouse_element": spouse_element.value if spouse_element else None,
            "predicted_appearance": appearance,
        }

    @staticmethod
    def _analyze_spouse_palace(
        pillars: Dict[str, Tuple[str, str]],
        day_branch: str,
        day_stem: str,
    ) -> Dict[str, Any]:
        """
        分析配偶宫（日支）。
        日支为配偶宫，代表配偶的基本状态和婚姻宫位的稳定程度。
        """
        day_element = STEM_ELEMENTS[day_stem][0]
        branch_element, branch_polarity = BRANCH_ELEMENTS[day_branch]
        hidden_stems = BRANCH_HIDDEN_STEMS.get(day_branch, [])

        # 日支与日干的关系
        relationship = "中性"
        if branch_element == day_element:
            relationship = "比和（日支与日干同气，配偶与己身相似）"
        elif GENERATION_CYCLE.get(branch_element) == day_element:
            relationship = "相生（日支生日干，配偶对己身有助力）"
        elif GENERATION_CYCLE.get(day_element) == branch_element:
            relationship = "泄秀（日干生日支，己身对配偶有付出）"
        elif DESTRUCTION_CYCLE.get(branch_element) == day_element:
            relationship = "相克（日支克日干，配偶对己身有约束）"
        elif DESTRUCTION_CYCLE.get(day_element) == branch_element:
            relationship = "制化（日干克日支，己身可驾驭配偶）"

        # 配偶宫稳定性
        stability = "稳定"
        stability_notes: List[str] = []

        for clash_pair in SIX_CLASH:
            if day_branch in clash_pair:
                other_branch = (
                    clash_pair[1] if clash_pair[0] == day_branch else clash_pair[0]
                )
                for p_name, (_, b) in pillars.items():
                    if p_name != "day" and b == other_branch:
                        stability = "不稳（日支逢冲）"
                        stability_notes.append(
                            f"日支{day_branch}与{p_name}支{b}相冲，配偶宫动荡"
                        )
                        break

        # 配偶宫性格特征
        personality = BRANCH_PERSONALITY.get(day_branch, "需结合全局判断")

        return {
            "day_branch": day_branch,
            "day_branch_element": branch_element.value,
            "day_branch_polarity": branch_polarity.value,
            "hidden_stems": hidden_stems,
            "relationship_to_day_master": relationship,
            "stability": stability,
            "stability_notes": stability_notes,
            "spouse_personality_hint": personality,
        }

    @staticmethod
    def _assess_marriage_quality(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        day_branch: str,
        is_male: bool,
    ) -> Dict[str, Any]:
        """
        评估婚姻质量。
        综合考虑：配偶星状态、日支状态、合冲关系、十神配置。
        """
        score = 70  # 基准分
        notes: List[str] = []

        # 1. 配偶宫（日支）与日干关系加分
        day_element = STEM_ELEMENTS[day_stem][0]
        branch_element = BRANCH_ELEMENTS[day_branch][0]

        if branch_element == day_element:
            score += 5
            notes.append("日支与日干同五行，按本规则加5分；不由此判断夫妻同心")
        elif GENERATION_CYCLE.get(branch_element) == day_element:
            score += 8
            notes.append("日支五行生日干，按本规则加8分；不等同配偶实际助力")
        elif DESTRUCTION_CYCLE.get(branch_element) == day_element:
            score -= 5
            notes.append("日支五行克日干，按本规则减5分；仅是盘内生克关系")

        # 2. 检查天干合
        stems = [pillars[p][0] for p in ["year", "month", "day", "hour"]]
        stem_combinations = [
            ("甲", "己"),
            ("乙", "庚"),
            ("丙", "辛"),
            ("丁", "壬"),
            ("戊", "癸"),
        ]
        for i in range(len(stems)):
            for j in range(i + 1, len(stems)):
                pair = frozenset((stems[i], stems[j]))
                if any(pair == frozenset(c) for c in stem_combinations):
                    if i == 1 and j == 2:  # 月干与日干合
                        score += 5
                        notes.append(
                            "月干与日干符合五合配对，按本规则加5分；未认证合化或感情基础"
                        )
                    elif i == 2 and j == 3:  # 日干与时干合
                        score += 3
                        notes.append(
                            "日干与时干符合五合配对，按本规则加3分；不预测晚年感情"
                        )

        # 3. 检查地支六合（日支参与）
        all_branches = [pillars[p][1] for p in ["year", "month", "day", "hour"]]
        for i, b in enumerate(all_branches):
            if b != day_branch and frozenset((day_branch, b)) in SIX_HARMONY:
                p_name = ["year", "month", "day", "hour"][i]
                if p_name in ["month", "hour"]:
                    score += 6
                    notes.append(
                        f"日支与{p_name}支六合，按本规则加6分；不直接判断现实关系和谐"
                    )

        # 4. 伤官见官扣分（女命尤忌）
        if not is_male:
            has_shangguan = False
            has_zhengguan = False
            for e in iter_pillar_gods(pillars, day_stem, skip_day_pillar=True):
                if e.ten_god == TenGod.HURT_OFFICER:
                    has_shangguan = True
                if e.ten_god == TenGod.POSITIVE_OFFICER:
                    has_zhengguan = True
            if has_shangguan and has_zhengguan:
                score -= 10
                notes.append(
                    "女命口径检测到伤官与正官共现，按本规则减10分；未审制化救应"
                )

        # 5. 比劫重重扣分
        bijie_count = sum(
            e.weight
            for e in iter_pillar_gods(pillars, day_stem, skip_day_pillar=True)
            if e.ten_god in (TenGod.COMPARE, TenGod.ROB_WEALTH)
        )
        if bijie_count >= 3:
            score -= 8
            notes.append("非日柱比劫计数达到本规则阈值，减8分；不能推断第三者或忠诚")

        # 限制分数范围
        score = max(30, min(95, score))

        # 质量等级
        if score >= 85:
            quality_level = "上等"
        elif score >= 70:
            quality_level = "中等"
        elif score >= 55:
            quality_level = "中下"
        else:
            quality_level = "需注意"

        return {
            "score": score,
            "score_kind": "traditional_rule_index",
            "score_basis": "70为基准，按声明的生克与配对固定加减并限制30–95；不是实际婚姻质量或成败概率。",
            "counting_scope": "历史评分的十神计数不含日柱；完整配偶星位置另含日支藏干，两者不可互作旺衰。",
            "quality_level": quality_level,
            "notes": notes,
        }

    @staticmethod
    def _check_marriage_shensha(
        pillars: Dict[str, Tuple[str, str]],
    ) -> List[Dict[str, str]]:
        """检查婚姻相关神煞。"""
        year_branch = pillars["year"][1]
        day_branch = pillars["day"][1]
        entries: List[Dict[str, str]] = []

        # 红鸾天喜已在 shensha 模块中，这里做婚姻专用解读
        hong_luan_map = {
            "子": "卯",
            "丑": "寅",
            "寅": "丑",
            "卯": "子",
            "辰": "亥",
            "巳": "戌",
            "午": "酉",
            "未": "申",
            "申": "未",
            "酉": "午",
            "戌": "巳",
            "亥": "辰",
        }
        tian_xi_map = {
            "子": "酉",
            "丑": "申",
            "寅": "未",
            "卯": "午",
            "辰": "巳",
            "巳": "辰",
            "午": "卯",
            "未": "寅",
            "申": "丑",
            "酉": "子",
            "戌": "亥",
            "亥": "戌",
        }

        hl = hong_luan_map.get(year_branch)
        tx = tian_xi_map.get(year_branch)
        if hl and hl in {b for _, b in pillars.values()}:
            entries.append(
                {
                    "name": "红鸾",
                    "position": f"年支{year_branch}查",
                    "meaning": f"红鸾在{hl}，主婚恋喜事",
                }
            )
        if tx and tx in {b for _, b in pillars.values()}:
            entries.append(
                {
                    "name": "天喜",
                    "position": f"年支{year_branch}查",
                    "meaning": f"天喜在{tx}，主感情顺遂",
                }
            )

        # 咸池（桃花）
        peach_map = {
            "申": "酉",
            "子": "酉",
            "辰": "酉",
            "寅": "卯",
            "午": "卯",
            "戌": "卯",
            "亥": "子",
            "卯": "子",
            "未": "子",
            "巳": "午",
            "酉": "午",
            "丑": "午",
        }
        peach = peach_map.get(day_branch)
        if peach and peach in {b for _, b in pillars.values()}:
            entries.append(
                {
                    "name": "咸池（桃花）",
                    "position": f"日支{day_branch}查",
                    "meaning": f"咸池在{peach}，主异性缘佳，需防烂桃花",
                }
            )

        # 孤辰寡宿
        gu_chen_map = {
            "子": "寅",
            "丑": "寅",
            "寅": "巳",
            "卯": "巳",
            "辰": "巳",
            "巳": "申",
            "午": "申",
            "未": "申",
            "申": "亥",
            "酉": "亥",
            "戌": "亥",
            "亥": "寅",
        }
        gua_su_map = {
            "子": "戌",
            "丑": "戌",
            "寅": "丑",
            "卯": "丑",
            "辰": "丑",
            "巳": "辰",
            "午": "辰",
            "未": "辰",
            "申": "未",
            "酉": "未",
            "戌": "未",
            "亥": "戌",
        }
        gc = gu_chen_map.get(day_branch)
        gs = gua_su_map.get(day_branch)
        if gc and gc in {b for _, b in pillars.values()}:
            entries.append(
                {
                    "name": "孤辰",
                    "position": f"日支{day_branch}查",
                    "meaning": f"孤辰在{gc}，主性格独立，婚姻较晚",
                }
            )
        if gs and gs in {b for _, b in pillars.values()}:
            entries.append(
                {
                    "name": "寡宿",
                    "position": f"日支{day_branch}查",
                    "meaning": f"寡宿在{gs}，主内心孤独感，需主动经营感情",
                }
            )

        return entries

    @staticmethod
    def _predict_marriage_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        day_branch: str,
        is_male: bool,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        推断婚期。
        核心逻辑：
        - 男命看财星出现的大运/流年
        - 女命看官星出现的大运/流年
        - 日支逢合的年份
        - 红鸾天喜到位的年份
        """
        timing_signals: List[str] = []

        # 大运流年中的配偶星信号
        if dayun_pillar:
            d_stem, d_branch = dayun_pillar
            d_god = get_ten_god(day_stem, d_stem)
            if is_male and d_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                timing_signals.append(f"大运{d_stem}{d_branch}见财星，有婚恋机会")
            elif not is_male and d_god in (
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
            ):
                timing_signals.append(f"大运{d_stem}{d_branch}见官星，有婚恋机会")

            # 日支逢合（确保两个地支不同且构成六合）
            if (
                d_branch != day_branch
                and frozenset((day_branch, d_branch)) in SIX_HARMONY
            ):
                timing_signals.append(
                    f"大运支{d_branch}与日支{day_branch}六合，婚姻宫被引动"
                )

        if liunian_pillar:
            l_stem, l_branch = liunian_pillar
            l_god = get_ten_god(day_stem, l_stem)
            if is_male and l_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                timing_signals.append(f"流年{l_stem}{l_branch}见财星，当年有婚恋机遇")
            elif not is_male and l_god in (
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
            ):
                timing_signals.append(f"流年{l_stem}{l_branch}见官星，当年有婚恋机遇")

            # 流年支与日支合（确保两个地支不同且构成六合）
            if (
                l_branch != day_branch
                and frozenset((day_branch, l_branch)) in SIX_HARMONY
            ):
                timing_signals.append(
                    f"流年支{l_branch}与日支{day_branch}六合，婚姻宫被引动"
                )

            # 红鸾天喜流年
            hong_luan_map = {
                "子": "卯",
                "丑": "寅",
                "寅": "丑",
                "卯": "子",
                "辰": "亥",
                "巳": "戌",
                "午": "酉",
                "未": "申",
                "申": "未",
                "酉": "午",
                "戌": "巳",
                "亥": "辰",
            }
            tian_xi_map = {
                "子": "酉",
                "丑": "申",
                "寅": "未",
                "卯": "午",
                "辰": "巳",
                "巳": "辰",
                "午": "卯",
                "未": "寅",
                "申": "丑",
                "酉": "子",
                "戌": "亥",
                "亥": "戌",
            }
            year_branch = pillars["year"][1]
            hl = hong_luan_map.get(year_branch)
            tx = tian_xi_map.get(year_branch)
            if l_branch == hl:
                timing_signals.append(f"流年{l_branch}为红鸾到位，主婚恋喜事")
            if l_branch == tx:
                timing_signals.append(f"流年{l_branch}为天喜到位，主感情顺遂")

        # 早婚/晚婚倾向判断
        timing_cues = set()
        tendency_notes: List[str] = []

        spouse_gods = (
            (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH)
            if is_male
            else (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER)
        )
        star_label = "财星" if is_male else "官星"
        # Opposite positional cues coexist; insertion order is not a rule for
        # adjudicating them. Preserve both without inventing a priority.
        for p_name, cue, note in (
            ("year", "偏早", f"{star_label}在年柱，早婚倾向"),
            ("hour", "偏晚", f"{star_label}在时柱，晚婚倾向"),
        ):
            if get_ten_god(day_stem, pillars[p_name][0]) in spouse_gods:
                timing_cues.add(cue)
                tendency_notes.append(note)
        marriage_tendency = (
            "早晚信号并存，未裁定"
            if len(timing_cues) == 2
            else next(iter(timing_cues)) if timing_cues else "正常"
        )

        return {
            "timing_signals": timing_signals,
            "marriage_tendency": marriage_tendency,
            "tendency_notes": tendency_notes,
        }

    @staticmethod
    def _identify_risk_factors(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        day_branch: str,
        is_male: bool,
    ) -> List[Dict[str, str]]:
        """识别婚姻风险因素。"""
        risks: List[Dict[str, str]] = []

        # 1. 日支逢冲
        for clash_pair in SIX_CLASH:
            if day_branch in clash_pair:
                other = clash_pair[1] if clash_pair[0] == day_branch else clash_pair[0]
                for p_name, (_, b) in pillars.items():
                    if p_name != "day" and b == other:
                        risks.append(
                            {
                                "type": "日支逢冲",
                                "severity": "高",
                                "description": f"日支{day_branch}与{p_name}支{b}相冲，婚姻宫动荡，需注意感情稳定性",
                            }
                        )
                        break

        # 2. 伤官见官（女命）
        if not is_male:
            has_shangguan = False
            has_zhengguan = False
            for p_name, (stem, branch) in pillars.items():
                if p_name == "day":
                    continue
                god = get_ten_god(day_stem, stem)
                if god == TenGod.HURT_OFFICER:
                    has_shangguan = True
                if god == TenGod.POSITIVE_OFFICER:
                    has_zhengguan = True
            if has_shangguan and has_zhengguan:
                risks.append(
                    {
                        "type": "伤官见官",
                        "severity": "高",
                        "description": "女命口径见伤官与正官共现；制化与救应未裁定，不由此断感情结果",
                    }
                )

        # 3. 比劫争财（男命）
        if is_male:
            bijie_count = 0
            for p_name, (stem, branch) in pillars.items():
                if p_name == "day":
                    continue
                god = get_ten_god(day_stem, stem)
                if god in (TenGod.COMPARE, TenGod.ROB_WEALTH):
                    bijie_count += 1
            if bijie_count >= 3:
                risks.append(
                    {
                        "type": "比劫争财",
                        "severity": "中",
                        "description": "男命非日干三处比劫的盘内计数信号；不推断第三者或伴侣忠诚",
                    }
                )

        # 4. 配偶星入墓
        spouse_stem_set: set = set()
        day_element = STEM_ELEMENTS[day_stem][0]
        if is_male:
            # 男命财星为配偶星
            wealth_element = DESTRUCTION_CYCLE[day_element]
            spouse_stem_set = {
                s for s, (e, _) in STEM_ELEMENTS.items() if e == wealth_element
            }
        else:
            # 女命官杀为配偶星：克日主（即天干五行能克制日主元素）的天干。
            for s, (e, _) in STEM_ELEMENTS.items():
                if DESTRUCTION_CYCLE.get(e) == day_element:
                    spouse_stem_set.add(s)
        tomb_map = {
            "辰": {"壬", "癸"},
            "戌": {"丙", "丁"},
            "丑": {"庚", "辛"},
            "未": {"甲", "乙"},
        }
        for p_name, (stem, branch) in pillars.items():
            if stem in spouse_stem_set and branch in tomb_map:
                if stem in tomb_map[branch]:
                    risks.append(
                        {
                            "type": "配偶星入墓",
                            "severity": "中",
                            "description": f"配偶星{stem}在{p_name}支{branch}符合本表墓库对应；不据此判断配偶健康或现实处境",
                        }
                    )

        return risks

    @staticmethod
    def _generate_suggestions(
        spouse_star: Dict[str, Any],
        spouse_palace: Dict[str, Any],
        marriage_quality: Dict[str, Any],
        marriage_shensha: List[Dict[str, str]],
        risk_factors: List[Dict[str, str]],
        is_male: bool,
    ) -> List[str]:
        """生成婚姻建议。"""
        suggestions: List[str] = []

        suggestions.append(
            "本次分数是盘内固定规则指数；结婚时间与相处安排需依据双方意愿、实际沟通及生活条件。"
        )

        # 基于配偶宫稳定性
        if "不稳" in spouse_palace.get("stability", ""):
            suggestions.append("配偶宫逢冲，建议婚前充分了解，婚后保持适当个人空间")

        # 基于风险因素
        high_risks = [r for r in risk_factors if r.get("severity") == "高"]
        if high_risks:
            suggestions.append(
                "盘内存在待复核的关系信号；先核对是否与实际互动相符，再讨论沟通和边界。"
            )

        # 基于神煞
        shensha_names = {s["name"] for s in marriage_shensha}
        if "孤辰" in shensha_names or "寡宿" in shensha_names:
            suggestions.append(
                "孤辰／寡宿仅是已命中的传统神煞标签；不据此给性格或婚姻结局定性。"
            )

        if not suggestions:
            suggestions.append("婚姻运势平稳，顺其自然即可")

        return suggestions
