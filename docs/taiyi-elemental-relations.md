# 太乙二目五行相关

`elemental_guan_assessment`按同次盘的文昌、始击实际十六神位置读取五行，再分别计算主克客、客克主、主生客、客生主、同类。它补齐此前缺少的二目五行片段；旧全局patterns和卷四五将三项继续使用其原来的空间关系，本项不往那里追加一个同名“关”。

## 同名相关，依据不同

[金镜卷三](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03)有将目同宫数齐的关；[卷四推主客相关法](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷04#推主客相闗法)另言以五行相制，并明写日计纳音。此前空间关没有命中，不能据此说二目不存在五行相制。

[图书集成所录淘金歌“定胜负”](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第687卷#定勝負)明确列出十六神五行：金三、木三、水二、火二、土六。这里按该表读取二目所在之神，不用六十甲子日柱纳音去替换。本项仅实现此片段，`full_daily_na_yin_method_verified=false`，不据片段声称完整日计纳音已经重建。

卷四两例分别为地目高丛木、天目太蔟金，以及地目阴主土、天目地主水。以卷二在地文昌属主、在天始击属客补核本段，两例分别对应客克主、主克客；不能将卷三立成表的“天目”栏目一词全局固定为主方。淘金歌另用主目、客目，释运仪的上下目称名另有表述；原称名按出处保留，当前盘仍明确文昌为主、始击为客。

角色只是盘内主客，不能自动把主方当成用户、客方当成另一人。现实人物、动静先后与其他主客情境仍需另外核对。

## 计算与原断分开

每个二目事实给出camp、role、actual_path、position、source_name和element。文昌回指本盘wenchang_palace，始击回指core_board.shiji。旧空间关以implemented_spatial_guan.pattern_paths另列，路径也回指同盘，不拿旧列表的缺项证明所有版本无关。

`relation`、`elemental_control`和`controlling_camp`只是五行关系。原文的主胜、客胜、三阵平及金土相生和解只放在`source_interpretation`，其`overall_outcome_assessed=false`。金土一例仅作同类元素关系参照，其他相生不套成“必和解”，也不转成概率、实际胜败或五将三项结论。

年、月、日、时计均返回所选实际位置的关系，但同时标明calculation_mode和source_day_usage：日计为day_mode_selected_fragment_only；其他计法为reference_only_source_names_day_method。只给数值核心、没有时间层时为time_method_not_supplied，不默认为日计。二目位置缺失、中心或其他无效值时not_assessed，不猜五行。

## 来源与验收边界

实施前清单（本地数据：`../tests/fixtures/taiyi_jinjing_v19/manifest.json`）冻结十六神分类、卷四两例、淘金歌两例和独立手写的25项五行关系。NCL-06604图57核卷四两例；图书集成477册图73/74核十六神清单和两例跨页文字。

四条是位置/关系的文字例，不是四个有独立日期的完整命盘。20个源字段中8个位置是给定输入，不计作计算命中；8个元素和4个关系是计算输出。十六神分类是来源表条目，25项是合成图关系，256位置对和144循环盘是软件覆盖，分别统计，不相加为古例数量或准确率。当前四例的12项输出相符；144软件盘中39盘有五行相制而旧已实现空间关未命中，此数只说明两种谓词不同，不证明新历史案例。

规则作者FateBridge contributors，版本taojin_eyes_wuxing_fragment_v1@1.0.0；运行结果给出来源、作者、生成资料和初始清单指纹。原始材料、所有旧差异及完整要求继续保留。128格三门五将钤表、完整日计纳音及上下目跨版本称名、完整古历、全书断法和自由解释盲审仍未通过。

## 读取和复现

太乙elemental_relations、合参taiyi_elemental_relations是选字段视图名称，不能当计算参数。首读设strict_fields=true、include_snapshot_text=false；如有result_delivery，继续读同run，不另起盘补全文。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone +08:00 --calculation-mode day --no-use-true-solar-time \
  --strict-fields --fields taiyi.elemental_guan_assessment taiyi.calendar_summary
uv run --locked --extra dev python scripts/build_taiyi_elemental_relations.py --check
uv run --locked --extra dev python scripts/audit_taiyi_elemental_relations.py \
  --output /tmp/taiyi-elemental-relations.json
```

来源审计仍退出1，工程测试通过不替代上述完整验收。
