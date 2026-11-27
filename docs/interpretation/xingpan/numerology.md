# 河洛与邵子参评取证

指定河洛理数用 `heluo`，指定金锁银匙／参评数用 `canping`。两者有不同起数与时间轴，不因“邵子”一名合并为同一技法；具体参数以实际合同和[合同索引](../../contracts/README.md)为准。

> [!NOTE]
> 本页整合共用日期钟时、河洛理数、邵子参评配运与同次核验方法，按本次用户所问章节查阅即可；普通短答不应省略用户明确要求的来源、计算关系或文本释义。

- **释义与原典引用**：解释文本时给出实际可读关键词并用白话说明字词、传统意象与条件；缺文和未决条件保留，不编字。核对方法与原典依据时按同次 `schedule_basis` 区分实际采用规则、语境对照规则与现代日期约定，每条引文交代书目、版本／唯一书影身份与页码；来源目录不授予全书认证。
- **知识查询**：需查术语或原句时按需调用 `knowledge_catalog(domain="heluo"/"canping")` 与 `knowledge_read`（`line_texts` 如 `乾為天:1`、`text_cells` 如 `水.3330.male`），保留 `citation`、`provenance`、`reference_only` 与 `reference_details`；当前盘实际采用何法仍由同 run 的 `schedule_basis` 核对，知识查询中的 `actual_start_at=null` 不代表尚未起运。
- **出生钟面与性别**：首次核验保留 `input_normalized`、`numerology_evidence.birth_clock` 及实际卦爻／编号与所需选文。读取 `birth_clock.input_representation` 的 `supplied_text` 与 `calculation_defaults`，`uncertainty_interval=null` 不从 `HH:MM` 猜正负半分钟；显示到秒也不提升出生记录精度。两工具均须明确已知性别，不可补男命；读 `text_provenance` 分别核对爻辞、注文与诗歌，`yaoci_collation` 单次目校仍待独立复核。

## 共用日期与钟时

按本次输入及返回的 `birth_clock` 核对，不为普通现代已知钟时套用古历假设。

- **历法、时区与重复钟时**：`date` 按推算格里历读取（1582 年前不自动切换儒略历），`timezone` 省略仅约定固定 `+08:00`，不推定出生地或历史 `Asia/Shanghai`。重复钟时另传已确认 `birth_utc_offset=±HH:MM[:SS]` 并保留地区 `timezone`，读取 `birth_clock.timezone_spec/timezone_rules/civil_utc_offset_seconds/civil_daylight_saving_seconds` 与 `requested_utc_offset/civil_fold/civil_time_ambiguous/birth_instant_utc`；`fold` 仅标记先后，不作精度或吉凶分。真太阳时默认开启且须明确 `longitude`（`0°` 有效，不拿 `0°` 或上海补未知地点），缺经度时按用户确认改用钟表时或补经度。
- **四柱衔接与精度验收（`pillar_links`）**：问起月／起时衔接时读取 `pillar_links` 视图，按实际年柱与日柱核干组、头干和步数；`all_links_match=true` 只验证两条衔接，`complete_calendar_assessment=false` 不认证整套历法。默认 DE440 已对 1700—2300 逐年 24 节气作有限 TT 网格核对，仍不等于真实历史 UTC；原版 Swiss Moshier 与当前 `native` 修订分别按各自模型身份解释。
- **宋代原例与时辰交节**：解释宋代原例（如 1150 处暑、1155 白露、开禧 1206 大雪亥时跨节）时区分平气注历、现代太阳交节与实际用历归属；亥时完整区间跨交节时不取中点或补一分钟判定前后，子时在子正起算源日内分两段。新增命例保留地数 33／30、异文与交节矛盾；固定四柱手工阴阳令标 `explicit_half_year`，实际出生瞬间交节标 `solstice_instant`。

## 河洛理数取证

只展开用户所问技法，按对应公开视图取 `fields`，先连起输入、算子、返回事实与传统含义，再说明未证明部分。

- **体卦与移爻（`body_structure`）**：逐阶段核 `input_lines`、八条 `records.original_positions/arity/lines/name` 与 `whole_reversal`；六个三爻体和两个六爻卦不当八个互体合并纳音，`literal_case_match=true` 仅限所核渐卦原例。移第三爻到最上位不是翻转阴阳或后天换卦。
- **有援、爻位与众宗（`line_conditions`）**：读 `source_youyuan` 区分主本“陰爻位”与别本“陰位”（阳元堂、阴应爻不命中主本阴元堂、阳应爻式），旧 `yuanTang.youYing` 仅先天通用事实。众宗须五同一异且元堂选中唯一异爻；`position_preference_order` 不是强弱分，`yuanTang.position_polarity_match` 的阴月当位仍未定义，未中正面式不推反面断语。
- **节候与源钟（`jiehou` / `clock_basis`）**：`jiehou` 按已算节气查四正卦爻，`selected_hou`、`selected_reconstruction_model` 与 `huagong_assessment` 为 `null` 时不补五日区间或当本命／岁卦。`clock_basis` 的 `year_context` 取本次实际年柱 `cycleYear`；卷一寅申巳亥九刻、其余八刻与六日进一支的 365 源日为相对推演，18 分一刻属另一等时假设，物理应用与完整映射为 `false` 时不推实际日卦应期。
- **属月与时令条件（`judge.month_affinity`）**：`time` 须为已知当地钟时（显式零点有效）。区分所属月与另述月份条件及离散／连续／跨年／季节语义，`month_label_match` 仅月号，附加条件未决时 `match=null`；十三条纳甲原句读同阶段 `natal_najia_clause`。乾八月、颐九月边界为空，随正月相反条件同时保留，无妄仍待核。
- **元堂、纳音与得体（`yuantang` / `body_relations`）**：`yuantang` 核对性别、时组、六位序列、`half_year.value/basis` 与换卦；`counterfactuals` 是半年敏感性比较而非两个实际出生盘。`body_relations` 读 `judge.deTi`，`present=null` 不自动断得体；第 51 页 `generating_qi`（卦体生纳音、无元气前提）与第 87 页 `mutual_generation` 分开。
- **元气与化工（`qi_phases`）**：`judge.qi_phases` 分开上下体、互体及取得／失去（旧并集字段不代表两阶段均有）；`fanYuan` 中 `rescue_match=null` 不推反中有救。`solar_term.boundary_context` 列当前节气、最近至点与下一四立，不扩充显式模型公开年份。
- **年命纳甲与数段（`najia` / `number_conditions`）**：`judge.najia` 中 `lines[].source.basis` 区分本卦已核与纯卦推演；`najia_collation` 与其余 51 卦待校分开，解卦末两支次序异文 `source_issues` 不换位；`deSheng` 不代替完整得时得位。`judge.seasonal_numbers` 区分正数、至弱／太过数段与 `seasonal_windows[].active`／`numeric_band_match`／`numeric_band_status`，重叠条件全保留，原数式名不作亲属、性格或生死断言。
- **岁运序号**：读 `heluo_timing.selected_annual/selected_month/selected_day` 与 `selected_texts`；`analysis_year` 为干支年标签，`month_index/day_index` 为原典序号而非公历 3 月 10 日。

## 邵子参评配运与原典

参评须明确出生时刻、时区与已知性别（不默认男命）；`method=gu` 取真实日支，显式 `ming` 为月支变法，`dayun_method` 默认 `bazi_appendix_v1`，不混称河洛六九年卦运。

- **首行、全运与年界（`timing_policy` / `calendar_boundaries`）**：首次按 `timing_policy` 视图取同次 `schedule_basis`、`first_row`、`first_period` 与 `selected`；旧法 `first_period=null` 仅表示无已核日期首运，不漏掉有实际编号与岁运条文的 `first_row`（`dayun[0]`）。全运读 `periods`，121 个立春读 `calendar_boundaries`。封装 DE440 独立年表登记 1700—2300 年，附法与连续法的 120 年序列另有具名有界立春许可（含 1699 年界与至 2420 年派生年界），不扩大独立年表范围或认证未来 UTC。
- **方法条款与原典引证（`schedule_basis`）**：按 `schedule_basis.profile_id` 与 `applied_clause_ids` 解释起运方向、折算与落点；连续法不执行整数借除，旧法不借附段认证实际日期。`schedule_basis.clauses` 按 `role` 区分目标采用条款、来源语境与另书子平背景；每条引文通过 `source_id` 连到 `schedule_basis.sources`，交代书名、版本／唯一书影链接或对象 ID 及页码，结合 `date_mapping_statement`、`calendar_mapping`、`age_conversion_result` 与 `future_clock_policy` 说明日期适用范围。
- **旧命宫、替支与目标查询**：显式旧命宫流年按实际出生年柱对应年标签起排（`liunian_series.birth_pillar_year/year_boundary/age_policy`）。核对参评替支时读 `canping_luck_substitution_v1` 轨迹与 PDF 64 释文，无查询时 `query_pair=null`。实际时刻查询用带时区 `analysis_datetime`，读 `canping_timing.selected` 与 `numerology_evidence.selected_texts`；`not_started` 不生成流年断语，`status=split` 必须按 `segments` 边界分段说明；120 行是干支年序覆盖。

## 同次交付与核验

未请求、未返回、未读取、未选择与未计算须分别说明：河洛未传 `analysis_year` 时仍生成 `heluo_timing.annual_rows`，仅 `selected_annual=null`；投影排除字段保留证据缺口，不另排一次冒充首次证据。

完整回执与全部选文首次即用 `detail=audit` 且 `fields=null`；仅核验时钟与核心字段时按 `fields` 精确投影：

```bash
python3 -m fatebridge.cli heluo --date 1990-05-15 --time 10:30 --longitude 116.40 --gender 男 --fields input_normalized numerology_evidence.birth_clock
```

无可用本地环境且非连接咨询时，保留核验缺口并交付已有可答部分，不猜解释器位置、不为咨询安装依赖。调用规范见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。
