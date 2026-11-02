# 太乙提挟几何与未决组合规则

`taiyi.enclosure_assessment`把所核的正宫提挟几何与尚未裁定的挟闭、四郭固、四郭杜分开。所有计法沿用同一盘的太乙、二目与主客四将；没有另起盘，也没有把几何命中改成事件胜负。

[《太乙金镜式经》卷三《推提挟法》](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03#推提挟法)李淳风条以太乙与将夹住正宫之目或将为提挟。[明钞本NCL-06604图51](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf#page=51)另有太元十年乙酉课例：太乙巽九、主大艮三，夹住卯四的始击与客大将。按完整物理方位，艮—卯—巽为相邻三正宫；数值3、4、9的大小关系不参与几何判断。

实现遍历太乙与每一主客大小将，把两者短弧中间的相邻正宫与本盘二目、四将逐一核对。每项提挟保留三条`basis`：太乙、夹将、被夹主体。中五没有环向，不能参与端点或被夹正宫；间神不先按八门扇区并入正宫，远隔长弧也不算。两个主体同在卯四时保留两个主体记录，仍只是一条古例。

`principal_enclosure.present=false`只表示未命中这条几何阅读。`unassessed`明确列出挟闭与四郭固杜；没有把未知记成不存在。`pattern_paths`指向同盘`patterns.N`，文本快照与结构化依据由同份结果生成。此层不改变卷四“五将三项”的合取条件，不把提挟单独当作“五将不发”。内外、囚死、绝气等配套断语和全部变体尚未完整核验。

## 同方大小二将夹持

V17新增同一方大小二将夹太乙或对方目将的分支，完整记录返回在enclosure_assessment.two_general_enclosure.patterns；pattern_paths指向这个同盘组件。原principal_enclosure只统计李法太乙与一将分支，原全局patterns及其路径保持不变，两算、将位、五将三值条件和门将合取不变。pattern_summary.pair_enclosures提供数量，提挟视图读取全部记录。

[淘金歌图70](https://zh.wikisource.org/wiki/Page:Gujin_Tushu_Jicheng,_Volume_477_(1700-1725).djvu/70)有两条明载课例：中平二年阳2主大酉、主参子夹太乙乾；建安三年阳15客大坤、客参乾夹太乙酉。所读图中计神只写“地”，保持未决，不展开为地主。年代标签和史事陈述不构成历法或现实预测验收。

二将为短弧两端，中间可以是正宫或其两侧间神。[阳19局注](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第694卷)以客大午、客参酉挟主目申，故不能只检查正中坤，亦不把申并入坤扇区。当前只核同方二将、太乙或对方目将；间神夹目几何不认证完整挟闭，跨阵二将、同方目将配对及后续内外囚死断法仍未裁定。同宫不同主体保留各自三条事实，不作独立源例计数。

V17初录清单（本地数据：`../tests/fixtures/taiyi_jinjing_v17/manifest.json`）在实现前冻结两条书影课例、全部阳72局转录中的17处“挟”字注记及人工主体读法。17注涉及11局16个唯一阵方/目标，阳27重复一目标；不能算17张独立命盘，更不等于72局全部断语已验收。两条课例核过书影；循环17注为原典转录，未冒认逐条核过书影。

初录把太簇、阴主、大威、大武映成错误支位，原始17项宫数/宫位只有13项相符。原JSON和清单不变，四处订正（本地数据：`../tests/fixtures/taiyi_jinjing_v17/name-map-corrections.json`）由独立卷二酉神太蔟、戌神阴主、午神大威、坤神大武原文支持，订正清单（本地数据：`../tests/fixtures/taiyi_jinjing_v17/correction-manifest.json`）绑定初录及名表证据。订正后17项相符；这不是4个新增课例，也没有为此更改生产算路。二将几何2/2与循环注17/17分别报告，原典总审计仍未通过。

规则作者FateBridge contributors，版本taojin_same_side_general_pair_v1@1.0.0；结构化与文本使用同一盘的事实和路径。可运行：

```sh
uv run --locked --extra dev python scripts/audit_taiyi_general_pairs.py --output /tmp/taiyi-general-pairs.json
```

脚本仍退出1，保留完整规则家族、全书、古历与完整断语未验收状态。

## 独立课例与订正记录

冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v11/manifest.json`）在实现前保留原图、11项宫数和2个明载提挟主体。初录（本地数据：`../tests/fixtures/taiyi_jinjing_v11/principal-enclosure.json`）把“天道”误转为亥，初次只有10/11项相符；卷二明载天道属未、大义属亥，因此用显式订正（本地数据：`../tests/fixtures/taiyi_jinjing_v11/transcription-correction.json`）更正名称映射。原图、初录与原清单全部保留，订正清单（本地数据：`../tests/fixtures/taiyi_jinjing_v11/correction-manifest.json`）同时约束初录清单和独立映射原文，生产算路没有为此修改。

订正后11项宫数及2个提挟主体相符，局序70另列核对。它们不是13条独立课例，也不认证古历。默认公共年计仍依赖通用农历范围，385年日期会拒绝；V12另有显式选择的[历史年计配置](taiyi-year-calendar.md)，以冻结历表完成所选五年日期适配，不自动扩展默认提供者。原V11接口回归用1969年相同72局相位核验几何和文本，不把现代相位重放称为古代日期验收。

“关”的对象也有版本差异：四库转录有将目，明钞图46只明列主客大小四将；四郭杜还涉及主参／主大异文。V11没有据一个词扩大五将判定；V13取得具体局注补证后增加文昌与将同宫的关及始击掩将，见[将目关系说明](taiyi-eye-relations.md)。四郭各分支的旧来源与未决理由仍见裁定记录（本地数据：`../tests/fixtures/taiyi_jinjing_v11/adjudication.json`），新增关掩并不认证固杜组合。月例朔月比较的假设性质详见[月计说明](taiyi-month.md)。

## 调用与验收

太乙`enclosures`、合参`taiyi_enclosures`视图首读保留范围、来源与所有参与主体的实际宫位。视图名不是请求参数，按任务复制其`fields`；完整载荷仍沿同run回执续读。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1969 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone '+08:00' --no-use-true-solar-time \
  --strict-fields --fields taiyi.enclosure_assessment taiyi.patterns
uv run --locked --extra dev python scripts/audit_taiyi_enclosures.py \
  --output /tmp/taiyi-enclosures.json
```

审计分别报告初录10/11、订正后11/11与2个几何主体。所选例通过不代表组合规则家族完成，脚本仍退出1。历法、全书符合、解释盲审与远程部署继续按总清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）验收。
