"""Explicit Mei Hua casting inputs; no inferred sounds, tones or observations."""

from typing import Annotated, Literal, Optional, Union

from pydantic import Field, StrictBool, StrictInt, model_validator

from .base import _DeferredModel
from .meihua_day_qi import MeihuaDayQiContext
from .meihua_situational import MeihuaResponseContext

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Trigram = Literal["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
Count = Annotated[StrictInt, Field(ge=1, le=1_000_000)]
Unit = Annotated[StrictInt, Field(ge=0, le=9)]
Whole = Annotated[StrictInt, Field(ge=0, le=1_000_000)]
Tone = Annotated[StrictInt, Field(ge=1, le=4)]


class SoundGroups(_DeferredModel):
    method: Literal["sound_groups"]
    first_count: Count = Field(description="First actually heard group of sounds")
    second_count: Count = Field(
        description="Second actually heard group; keep the order"
    )
    hour_branch: Branch
    line_sum_basis: Literal["raw_counts", "trigram_numbers"] = Field(
        default="raw_counts",
        description="Explicit convention for counts above eight; the worked example does not uniquely adjudicate this boundary",
    )


class ObjectCount(_DeferredModel):
    method: Literal["object_count"]
    count: Count = Field(
        description="Confirmed quantity of countable objects; no inferred scene count or arbitrary replacement number"
    )
    hour_branch: Branch = Field(
        description="Confirmed hour branch; no current-clock fallback"
    )
    line_sum_basis: Literal["raw_counts", "trigram_numbers"] = Field(
        default="raw_counts",
        description="Declared reading of 卦數 above eight: raw_counts uses count + hour number; trigram_numbers uses reduced UPPER trigram number + original hour number. Never reduce the hour to the lower-trigram number for the moving line. Both candidates are retained when they differ",
    )


class ObservedTrigrams(_DeferredModel):
    method: Literal["observed_trigrams"]
    upper_trigram: Trigram = Field(
        description="Confirmed trigram of the observed object/person; do not infer from an unseen scene"
    )
    lower_trigram: Trigram = Field(
        description="Confirmed trigram of the observed direction; use pre-heaven trigram numbers, not Luo Shu numbers"
    )
    hour_branch: Branch


class ObservedCategories(_DeferredModel):
    method: Literal["observed_categories"]
    subject_category: Literal[
        "elder_person", "young_person", "cow", "chicken", "dry_wood"
    ] = Field(
        description="Caller-confirmed category matching the selected NLC1925 duanfa examples: 老人/少年/牛/雞/槁木. Finite source lookup, no inferred scene classification, age cutoff, generic wood substitution or sound-method switching",
    )
    subject_description: str = Field(
        min_length=1,
        max_length=240,
        description="Actual caller-provided description or reference for the declared subject; never parsed to override explicit source-category or direction fields",
    )
    single_subject_confirmed: StrictBool = Field(
        json_schema_extra={"const": True},
        description="Caller explicitly confirms one selected subject. False, unknown and group sightings cannot enter this finite single-subject route; not an independent scene verification",
    )
    direction: Literal[
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    ] = Field(
        description="Confirmed named compass side used for the lower trigram; source chart uses east震/south離/west兌/north坎 and pre-heaven trigram numbers. No GPS bearing sector or north-reference conversion inferred"
    )
    direction_role: Literal["from", "toward", "at"] = Field(
        description="Meaning of the reported compass side: comes from, goes/falls toward, or is located at. Preserve this side; do not replace a source side with the opposite travel heading. Unknown relation must not be guessed"
    )
    hour_branch: Branch = Field(
        description="Confirmed hour branch used once in the moving-line sum; no current-clock fallback"
    )

    @model_validator(mode="after")
    def confirmed_single_subject(self) -> "ObservedCategories":
        if not self.single_subject_confirmed:
            raise ValueError(
                "所选端法类别入口须已确认单一对象；群物或未知不可默认一个对象"
            )
        if not self.subject_description.strip():
            raise ValueError("物象描述不能用空白替代未知事实")
        return self


class ZhangChi(_DeferredModel):
    method: Literal["length_zhang_chi"]
    zhang: Whole
    chi: Unit
    cun: Optional[Unit] = Field(
        default=None, description="Recorded but excluded from casting by 丈尺占"
    )

    @model_validator(mode="after")
    def nonzero(self) -> "ZhangChi":
        if self.zhang == self.chi == 0:
            raise ValueError("丈尺占的丈数和尺数不能同时为零；寸数不参与取卦")
        return self


class ChiCun(_DeferredModel):
    method: Literal["length_chi_cun"]
    chi: Whole
    cun: Unit
    fen: Optional[Unit] = Field(
        default=None, description="Recorded but excluded from casting by 尺寸占"
    )
    hour_branch: Branch

    @model_validator(mode="after")
    def nonzero(self) -> "ChiCun":
        if self.chi == self.cun == 0:
            raise ValueError("尺寸占的尺数和寸数不能同时为零；分数不参与取卦")
        return self


class MeihuaToneReference(_DeferredModel):
    encoding: Literal["ping_shang_qu_ru"] = Field(
        default="ping_shang_qu_ru",
        description="1/2/3/4 mean 平/上/去/入, never Mandarin pinyin tone numbers",
    )
    system_name: str = Field(
        min_length=1,
        max_length=240,
        description="Caller-declared phonological system or specific worked-example reading; not automatically authenticated",
    )
    source: str = Field(min_length=1, max_length=1000)
    reading_scope: Literal[
        "lexical_category", "reported_pronunciation", "worked_example"
    ]

    @model_validator(mode="after")
    def nonblank_reference(self) -> "MeihuaToneReference":
        if not self.system_name.strip() or not self.source.strip():
            raise ValueError(
                "四声依据的音系及来源不能只含空白；未确认时留空整个tone_reference"
            )
        return self


class TextTones(_DeferredModel):
    method: Literal["text_tones"]
    tones: list[Tone] = Field(
        min_length=4,
        max_length=10,
        description="One caller-supplied 平/上/去/入 category per character, encoded 1/2/3/4. Historical sound systems and the selected Meihua worked example can differ. Do not replace categories with modern Mandarin tone numbers or silently change the source system",
    )
    text: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=10,
        description="Optional original characters, only for matching the supplied categories",
    )
    tone_reference: Optional[MeihuaToneReference] = Field(
        default=None,
        description="Optional declared sound system, source and reading scope; absent means unknown, supplied means caller-declared rather than independently verified. No online dictionary lookup or automatic tone assignment",
    )

    @model_validator(mode="after")
    def matching_characters(self) -> "TextTones":
        if self.text is not None and len(self.text) != len(self.tones):
            raise ValueError("原字与四声类别须逐字对应；不自动猜音或删标点")
        return self


class TextStrokes(_DeferredModel):
    method: Literal["text_strokes"]
    strokes: list[Count] = Field(
        min_length=2,
        max_length=3,
        description="Confirmed strokes of each actual glyph; never replace an unusual glyph with a modern dictionary count",
    )
    text: Optional[str] = Field(default=None, min_length=2, max_length=3)

    @model_validator(mode="after")
    def matching_characters(self) -> "TextStrokes":
        if self.text is not None and len(self.text) != len(self.strokes):
            raise ValueError("原字与所报笔画须逐字对应")
        return self


class SingleCharacter(_DeferredModel):
    method: Literal["single_character_strokes"]
    script_style: Literal["regular"] = Field(
        description="The original method requires a legible regular-script glyph, not cursive"
    )
    left_strokes: Whole
    right_strokes: Whole
    total_strokes: Count
    text: Optional[str] = Field(default=None, min_length=1, max_length=1)

    @model_validator(mode="after")
    def complete_partition(self) -> "SingleCharacter":
        if self.left_strokes + self.right_strokes != self.total_strokes:
            raise ValueError("所报左右阴阳画须完整分配全字笔画，不猜或重复计画")
        return self


class TextCount(_DeferredModel):
    method: Literal["text_count"]
    character_count: StrictInt = Field(
        ge=11,
        le=1_000_000,
        description="Confirmed character count, no silent exclusions. The default fixed transcription is limited to100. Explicitnlc1925_selected_span preserves百餘字; counts above100 are labelled software extensions because its exact upper extent is unadjudicated.1million is a software guard, not a classical limit",
    )
    text_basis: Literal["fixed_transcription_2690596", "nlc1925_selected_span"] = Field(
        default="fixed_transcription_2690596",
        description="Explicit source choice: fixed transcription百字 or selected facsimile百餘字. Never switch source after seeing a result",
    )
    line_sum_basis: Literal["raw_counts", "trigram_numbers"] = Field(
        default="raw_counts",
        description="Declared reading of合二卦總數: sum raw character halves or their reduced trigram numbers; no hour added. Both distinct casts retained; not uniquely adjudicated by the selected span",
    )

    @model_validator(mode="after")
    def text_extent(self) -> "TextCount":
        if (
            self.text_basis == "fixed_transcription_2690596"
            and self.character_count > 100
        ):
            raise ValueError(
                "固定转录工作范围至100；影印百餘字须显式选择nlc1925_selected_span，且其精确上限未裁定"
            )
        return self


class ExistingCast(_DeferredModel):
    method: Literal["existing"]
    hexagram_code: str = Field(
        pattern=r"^[01]{6}$", description="Actual existing cast, bottom line first"
    )
    moving_line: StrictInt = Field(
        ge=1, le=6, description="The one actual moving line, bottom=1; never draw again"
    )


class LunarTimeAddedCount(_DeferredModel):
    method: Literal["lunar_time_added_count"]
    year_branch: Branch = Field(
        description="Confirmed lunar year branch; not a Gregorian year or Li Chun year pillar"
    )
    lunar_month: StrictInt = Field(
        ge=1,
        le=12,
        description="Caller-confirmed lunar month number; no date conversion or leap-month adjudication",
    )
    lunar_day: StrictInt = Field(
        ge=1,
        le=30,
        description="Caller-confirmed lunar day; this branch alone cannot validate the actual month's length",
    )
    hour_branch: Branch
    added_count: Count = Field(
        description="Confirmed added count, e.g. supplied surname count(s); never inferred from modern glyph strokes. Upper raw sum includes it, lower and moving-line sum add the original hour number once"
    )


MeihuaCasting = Annotated[
    Union[
        SoundGroups,
        ObjectCount,
        ObservedTrigrams,
        ObservedCategories,
        ZhangChi,
        ChiCun,
        TextTones,
        TextStrokes,
        SingleCharacter,
        TextCount,
        ExistingCast,
        LunarTimeAddedCount,
    ],
    Field(discriminator="method"),
]


class MeihuaWeatherContext(_DeferredModel):
    season: Optional[Literal["spring", "summer", "autumn", "winter"]] = Field(
        default=None,
        description="Confirmed season in the source's weather context; not inferred from a timezone or Gregorian month",
    )
    prior_condition: Optional[
        Literal["prolonged_rain", "prolonged_clear", "neither_prolonged"]
    ] = Field(
        default=None,
        description=(
            "Caller-confirmed prior weather: prolonged_rain, prolonged_clear, or "
            "neither_prolonged only when both prolonged conditions are confirmed false. "
            "None means unknown, never confirmed neither. The original gives no "
            "number of days for 久. No rainfall alone does not establish clear sky; "
            "a completed dry day, a missing observation or a cast cannot supply this fact"
        ),
    )
    many_min_count: Optional[StrictInt] = Field(
        default=None,
        ge=2,
        le=6,
        description="Declared software threshold for 多, with both six-position and five-role static-once scope probes retained. The raw six-position status is qualified when scopes disagree; neither scope is claimed as uniquely classical. If absent, potentially applicable 多 conditions remain pending",
    )


class MeihuaExternalObservation(_DeferredModel):
    manifestation: Literal[
        "furnace_flame",
        "candle_flame",
        "red_purple_color",
        "sharp_metal_tool",
        "metal_ornament_or_utensil",
        "actual_water",
        "black_or_damp_appearance",
        "soil",
        "fired_pottery",
        "cut_firewood",
        "living_tree",
        "gold_silver_treasure",
        "weapon",
    ] = Field(
        description="Caller-reported selected source category; gold_silver_treasure and weapon are explicit NLC1925內外論 classifications, never inferred from every metallic ornament or sharp tool, free text, favorable/unfavorable wishes or an unseen scene. Symbolic body qualification is separate from material effect, real-world safety and outcomes. Unknown manifestations cannot be guessed"
    )
    label: str = Field(
        min_length=1,
        max_length=240,
        description="Caller description/reference for this reported observation; presence and classification are not independently verified",
    )
    motion: Optional[Literal["moving", "stationary"]] = Field(
        default=None,
        description="Optional caller-reported actual motion of this external observation. Omit if unknown; never inferred from material, description, observer activity or inner symbolic roles. Moving water/carried soil and still wells/ground remain distinct. Does not determine omen valence or an event date",
    )

    @model_validator(mode="after")
    def nonblank_label(self) -> "MeihuaExternalObservation":
        if not self.label.strip():
            raise ValueError("外应资料须有已报描述，不能用空白代替未知事实")
        return self


class MeihuaObservationContext(_DeferredModel):
    label: str = Field(
        min_length=1,
        max_length=240,
        description="Caller reference for the same casting episode and observer. Not parsed to infer any condition; presence or perception is not independently verified",
    )
    quiet_room: Optional[StrictBool] = Field(
        default=None,
        description="Caller declaration of 在静室 for this cast; omit/null if unknown. Physical setting is not mental stillness or a decibel measurement",
    )
    nothing_heard: Optional[StrictBool] = Field(
        default=None,
        description="Caller declaration of no external 所闻 in the selected 静占 sense at this cast; omit/null if unknown. No inference from absent records or unimplemented categories",
    )
    nothing_seen: Optional[StrictBool] = Field(
        default=None,
        description="Caller declaration of no external 所见 in the selected 静占 sense at this cast; omit/null if unknown. No inference from an unseen scene, empty records or unimplemented categories",
    )

    @model_validator(mode="after")
    def nonblank_label(self) -> "MeihuaObservationContext":
        if not self.label.strip():
            raise ValueError("闻见语境须有已报说明，不能用空白代替未知")
        return self


class MeihuaReputationContext(_DeferredModel):
    label: str = Field(
        min_length=1,
        max_length=240,
        description="Caller reference for the declared source context; never parsed to infer office status, desired result or an appointment",
    )
    currently_in_office: Optional[StrictBool] = Field(
        default=None,
        description="Caller-confirmed 在任 in the selected historical official-office clause, not generic modern employment, seniority or a desired promotion. Omit/null if unknown; no real personnel or hazard verdict follows",
    )
    seeking_official_appointment: Optional[StrictBool] = Field(
        default=None,
        description="Caller confirms the question concerns the source's 職任之處. Not inferred from reputation, an exam, already being employed, question keywords or wishes. Omit/null if unknown; selected 方道 witnesses are not an actual location",
    )

    @model_validator(mode="after")
    def nonblank_label(self) -> "MeihuaReputationContext":
        if not self.label.strip():
            raise ValueError("求名情境须有已报说明，不能用空白代替未知事实")
        return self


class MeihuaInterpretationOptions(_DeferredModel):
    interpretation_topic: Literal[
        "general",
        "weather",
        "planning",
        "reputation",
        "wealth",
        "transaction",
        "travel",
        "meeting",
        "lost_property",
        "traveler",
        "household",
        "dwelling",
        "marriage",
        "dining",
    ] = Field(
        default="general",
        description="Explicit branch: general; weather (no body/use); planning/reputation/wealth/transaction (文明书局本原四章初始体用条款，wealth另列求财成分)；travel/meeting为同本出行/谒见章，travel另核旺气及辅助生体偏好，多字及舟陆角色范围未裁定；lost_property为失物章五种初始关系及明示变用经卦读法的方位类象，物不失不否认已报遗失，位置与寻获未核实。traveler为行人章，返归句保留原体参照，在外补充明示以初用为受生受克对象，四个其他内卦角色逐一列出；初用月令衰与受克须同时成立，未知不猜，多字门槛及完整角色范围未裁定，不生成行踪、灾祸、返归核实或日期。reputation另列求名补充句及原文時序/方道，reputation_context声明原文在任与求职任条件，未知不猜，巽方道東/同本地理及转录東南等差异未裁定。household/dwelling分别为家宅/屋舍章，沿用实际原体与初用。家宅比利/转录比和未裁定，五行相同不自动套家宅安稳句；屋舍保留冷退/衰退异文。家宅生体转引人事章只核所列四内卦实际角色，未作完整跨章合参、住宅安全鉴定、选房或迁居许可。marriage为婚姻章五种初始关系，并分别核原体所占之家、初用所婚之家的已报节月旺气条件；原文未定与缺月令保持未知。补充生体/体生只列实际关系成分，或字不合并成必然同现；后段比利/转录比和未裁定，不自动套彼此相就句。八卦相貌品行仅作历史文本记录，不指派现实人物特征、两家财富、意愿或婚姻成败。dining为飲食章五种初始关系，并另列内卦坎酒、兑食及體用類的坤艮制坎、离制兑；这些句不要求多字门槛，不因制约者受制或季令衰自动抵消，完整内外合参未裁定。影印生身/转录生体及兑坎组合未裁定，不把酒食象当实际供应、菜单、席上人物、饮酒或饮食医疗建议。版本异文另列。Question keywords never switch branches; historical clauses are not hazard verdicts, travel instructions, validated outcomes or event dates",
    )
    weather_context: Optional[MeihuaWeatherContext] = Field(
        default=None,
        description="Optional caller-confirmed season and weather declarations, only with interpretation_topic=weather. Omit unknown facts; these conditions qualify the selected classical weather clauses.",
    )
    reputation_context: Optional[MeihuaReputationContext] = Field(
        default=None,
        description="Optional caller-confirmed 在任 and 職任之處 declarations, only with interpretation_topic=reputation. Unknown omit/null; no keyword inference, permission, event date, validated outcome or probability",
    )
    observation_context: Optional[MeihuaObservationContext] = Field(
        default=None,
        description="Optional same-cast/observer quiet-room and hearing/vision declarations for human branches. Missing is uncollected, not confirmed absent. Selected NLC1925静占 conditions only; no full year-month-day strength synthesis, mental-state inference, casting eligibility or validated forecast. Never changes old study denominators",
    )
    response_context: Optional[MeihuaResponseContext] = Field(
        default=None,
        description="Optional caller-reported same-cast 方應/天時應/地理應/人事應 for human matters. No scene, direction or weather inferred; retain multiple trigram candidates and source variants. Not a casting method, future weather forecast, combined ten-response verdict, probability or event date",
    )
    observer_activity: Optional[Literal["seated", "walking", "standing"]] = Field(
        default=None,
        description="Optional caller-confirmed observer activity corresponding to selected NLC1925 我坐/我行/我立. Omit if unknown; no inference from question, vehicle motion, external movement or mental stillness. Selected relative wording only, no measured delay, omen valence, or date. Human-matter branches only",
    )
    matter_scenario: Optional[Literal["favorable_matter", "unfavorable_matter"]] = (
        Field(
            default=None,
            description="Caller-confirmed subject category for the selected 占卦訣: 原文问吉事 or 原文问不吉之事. Not a desired answer, question sentiment, topic classification or prediction of an actual outcome. Omit when unknown. Human-matter branches only; declaration is not independently verified",
        )
    )
    external_observations: Optional[list[MeihuaExternalObservation]] = Field(
        default=None,
        min_length=1,
        max_length=12,
        description="Optional caller-reported manifestations for general/planning/reputation/wealth/transaction/travel/meeting/lost_property/traveler/household/dwelling/marriage/dining; NLC1925 selected material-versus-appearance qualifications plus explicit gold_silver_treasure/weapon original-body symbolic cases. Traveler observations keep the original-body reference and are not automatically rebased to initial use. Not every metal object is treasure or every sharp tool a weapon. Omit if unknown; no default observations, unique trigram assignment, physical/hazard/clinical verdict or event date.12 is a software guard, not a classical limit",
    )

    @model_validator(mode="after")
    def context_matches_topic(self) -> "MeihuaInterpretationOptions":
        if (
            self.reputation_context is not None
            and self.interpretation_topic != "reputation"
        ):
            raise ValueError(
                "reputation_context须与interpretation_topic=reputation一起提供"
            )
        if self.response_context is not None:
            if self.interpretation_topic == "weather":
                raise ValueError("所选十应体用现场条件仅用于人事分支，不能套用天时占")
            self.response_context.validate_quiet_context(
                self.observation_context.model_dump(mode="json")
                if self.observation_context is not None
                else None
            )
        if self.observation_context is not None:
            if self.interpretation_topic == "weather":
                raise ValueError("所选静占体用语境仅用于人事分支，不能套用天时占")
            if self.external_observations is not None and all(
                getattr(self.observation_context, key) is True
                for key in ("quiet_room", "nothing_heard", "nothing_seen")
            ):
                raise ValueError("同次静室且无所闻见的声明不能同时附带已报外应资料")
        if (
            self.observer_activity is not None
            and self.interpretation_topic == "weather"
        ):
            raise ValueError("observer_activity仅用于所选人事动静条款，不能套用天时占")
        if self.matter_scenario is not None and self.interpretation_topic == "weather":
            raise ValueError(
                "matter_scenario仅为人事原文情境声明，不能用于不分体用的天时占"
            )
        if self.weather_context is not None and self.interpretation_topic != "weather":
            raise ValueError("weather_context须与interpretation_topic=weather一起提供")
        if (
            self.external_observations is not None
            and self.interpretation_topic == "weather"
        ):
            raise ValueError("所选外应体用资格仅用于人事分支，不能套用天时占")
        return self


class MeihuaCastRequest(MeihuaInterpretationOptions):
    day_qi_context: Optional[MeihuaDayQiContext] = Field(
        default=None,
        description="Optional caller-confirmed day branch for selected NLC1925日應/month-day strength clauses. No datetime is inferred from hour/year/lunar day/question; missing stays uncollected. A declared day boundary without a civil date is not independently verified. Human branches only; no full year-month-day synthesis or validated forecast",
    )
    casting: MeihuaCasting = Field(
        description="Confirmed casting input. Select method explicitly and supply its observed counts, trigrams or existing hexagram; the method determines the required fields.",
    )
    season_month_branch: Optional[Branch] = Field(
        default=None,
        description="Optional independently resolved solar-term month branch. If unknown, seasonal strength stays unavailable; no date/time is invented",
    )
    question: Optional[str] = Field(
        default=None, description="One question; does not alter the supplied cast"
    )

    @model_validator(mode="after")
    def observation_matches_casting(self) -> "MeihuaCastRequest":
        if self.day_qi_context is not None and self.interpretation_topic == "weather":
            raise ValueError("所选日气体用条款仅用于人事分支，不能套用天时占")
        if self.observation_context is not None:
            from fatebridge.core.meihua_observation import (
                ensure_observation_method_context,
            )

            ensure_observation_method_context(
                self.casting.method,
                self.observation_context.model_dump(mode="json"),
            )
        return self
