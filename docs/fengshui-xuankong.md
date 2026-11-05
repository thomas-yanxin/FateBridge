# 玄空运山向宅盘：版本、输入和验证

[文档中心](README.md) · [风水总览](fengshui.md) · [请求示例](examples/README.md)

生成玄空数字宅盘，需要有依据的历史宅运与坐向。调用者可以追溯规则版本、核对九宫计算，并在资料支持时启用有限解释，用于空间咨询或应用集成。

`fengshui_xuankong_natal` 的 REST 入口为 `POST /api/fengshui/xuankong_natal`，MCP 与 CLI 同名。选定版本 `xuankong_zhongzhou_v1@1.4.0` 完整计算九宫运星、山星、向星，支持下卦和中州派兼向替星。与 `layers.annual_stars` 独立；查询年份变化不改变历史宅盘。基础三法合同见[家居风水](fengshui.md)。

调用时先准备[历史定运与角度资料](#定运校验与角区实现)，再运行[三端示例](#三端调用)。已有数字盘需要进一步解释时，单独启用[有限解释](#显式启用有限解释)；维护者可从[独立验证](#独立验证与复现)追溯固定样本及版本分歧。

## 规则数据与版本维护

规则来源、选版差异、二十四山和替星表统一维护在 [skill 的历史宅盘参考](../skills/onda-fengshui/references/xuankong.md)。

生产规则为离线 [xuankong-v1.json](../src/fatebridge/data/fengshui/xuankong-v1.json)，与基础规则数据及其版本分别维护。规则语义变化须另建版本及独立样本；1.0.1 修复既定角区的浮点实现与不确定输入处理，五黄和替星表未改。

1.2.0把替星表完整登记为24项，明确区分13改数与11同数；缺项不再默认回退原星。每侧 `replacement_lookup`说明下卦未用替、同数保留、实际替换或五黄不替。完整原典与作者语境见[替星依据](../skills/onda-fengshui/references/replacement-stars.md)，五幅原书完整九宫盘的135个数字独立核对通过，原有山／向／运数及兼向选择条件保持一致。

计算候选必须先通过宅运山向身份、九星排列、逐宫表示、中心星和顺逆飞行记录的一致性检查，才能进入结构解释。内部矛盾使整次调用返回 `fengshui_calculation_inconsistent`，不能丢弃异常候选后继续下结论；具体错误与原书差异的区别见计算盘异常处理。正常计算的数字规则及版本保持不变，这项工程检查不授予原典或预测有效性。

运行来源比较另采用 `shen_2011_natal_numeric_comparison_v2@2.0.0`，逐候选核对指定整理本216下卦正文、216下卦图和216起星图。替卦原图的三个数字差异及卷五编者范围随盘返回；起星正文、星名与兼向选盘条件未验证。它不改变中州起盘版本或候选选择，不能将局部图数相合扩大为整套技法符合；详见运行来源比较。

## 三端调用

按[快速入门](getting-started.md)安装后，从仓库根目录运行。REST 需先启动服务，并按服务配置提供 API Key。

示例按用途汇总于[请求索引](examples/README.md)。可复制 [独立宅盘请求](examples/fengshui-xuankong.json) 和 [基础三法＋宅盘＋年星合参](examples/fengshui-xuankong-with-annual.json)。

```json
{
  "house": {"object_id": "home", "facing_degrees": 255, "north_reference": "magnetic"},
  "period": {
    "basis": "construction_completion",
    "effective_event_year": 2004,
    "evidence": "已核实立春后竣工，按竣工事件定运"
  },
  "ruleset_id": "xuankong_zhongzhou_v1"
}
```

```bash
curl -X POST http://localhost:8010/api/fengshui/xuankong_natal \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/fengshui-xuankong.json

uv run --locked --extra dev fatebridge fengshui_xuankong_natal --request-file docs/examples/fengshui-xuankong.json
uv run --locked --extra dev fatebridge fengshui_assess --request-file docs/examples/fengshui-xuankong-with-annual.json
uv run --locked --extra dev fatebridge describe fengshui_xuankong_natal
```

MCP `fengshui_xuankong_natal` 的参数就是上面 JSON 对象。认证设置与其他REST端点一致；工具目录、发现接口、JSON输出schema、错误、字段投影和运行元数据均来自共用目录。CLI也支持 `--house '{...}' --period '{...}'`；请求文件保留未知字段供模型拒绝，不静默删除。

聚合需显式选择 `methods` 中的 `xuankong_natal`，并传 `xuankong` 请求。自动选法按场景与已知事实处理，不能假定每次都运行基础三法；详见[场景兼容与归一化](fengshui.md#场景兼容与归一化)。内层未提供 `house` 时继承顶层住宅；同时提供时必须一致。年星继续用顶层 `effective_year` 或 `query_at`；宅盘只用 `xuankong.period`，两者不互相补默认值。

## 定运校验与角区实现

定运事件、有效年、宅运三选一的输入语义，磁北、测量误差及边界候选的解释，见 [历史宅盘资料核对](../skills/onda-fengshui/references/xuankong.md#定运输入和不确定性)。请求字段及取值以共享 Schema 为准；三端使用同一校验路径。

事件有效年与宅运分别读取：立春保护区内 `effective_event_year=null`，候选年和暂取年单列；若全部候选年同运，宅盘仍可complete而年份保持待确认。跨运时无唯一宅盘，`timing.candidate_period_intervals` 保留候选历史运区间，见字段与示例。

公开1800–2199事件年所需的完整运区间端点可落在1784–2204。风水层在原打包模型范围外，按既定选择启用独立[历史DE440轨道扩展](fengshui.md)，逐端点保留实际模型及资料散列；公开输入范围不扩大。选定模型无法求根时返回错误；边界候选保护不替代1秒TT验收。

宅向误差在 `house.bearing_uncertainty_degrees` 提供，玄空上限为7.5°。同一测量在合参八宅层也保留支持坐卦，参见[共享误差与布局候选](../skills/onda-fengshui/references/house-bearing-uncertainty.md)。

1.0.1改为闭角区与测量闭区间的直接相交判断，不扩张浮点容差。所有24山的±4.5°、±7.5°均验证分界及两侧最近可表示浮点数；区间端点碰线也保留双侧候选。给定 `house.sitting_trigram` 时，用已确认坐卦约束候选宫位，避免跨宫误差盘与八宅已确认坐卦冲突；同宫内两山或下／替模式的歧义仍保留。

1.1.1进一步按已接收浮点数的精确有理数值计算误差上下界，避免浮点加减把实际未触线的端点舍入到分界并多造候选。这只修复数值实现，不认证物理测量达到相同精度，也不从角区长度产生概率。

## 输出分层与计算过程

`layers.xuankong_natal` 包含历史定运、住宅ID、测量依据与误差、24山表、唯一 `chart` 或多个 `candidates`。每盘都有独立 `period_chart`、`mountain_chart`、`facing_chart`，九宫 `palaces` 分别返回固定 `palace_number` 与三个星数；固定宫数不可当成运星。

规则1.4.0在各候选的 `structure.classical_patterns.opposite_star_comparison` 返回山星与对宫向星的八个有向配对，包含两端宫位、原数、数和及条件。中宫数字单列，不成为空间对宫；这与三组同宫求和、固定地盘比较和作者局名范围分别解释。来源X12为王亭之印刷例盘，不采用其中吉凶与应期断语。[数式规则](../skills/onda-fengshui/references/classical-patterns.md#山星与对宫向星的有向配对)和[固定释义1.2.0](../skills/onda-fengshui/references/calculation-reading.md)提供完整范围与同run核验方法。

`trace.mountain`、`trace.facing` 保留原入中星、借用的原星／宅运、同元龙山、阴阳、顺逆、最终入中星、是否发生数值替换与五黄政策。宫位飞行路径是 `C,NW,W,NE,S,N,SW,E,SE`；运盘始终顺飞，山向盘按各自原元龙阴阳顺逆。

1.1.0 的 `chart/candidates.*.structure` 返回历史宅运当运数的山、向星位置与星位结构，以及运／山／向三组逐宫合十比较。结构不随当前评价运改变，也不表示当前旺衰、外局匹配或现实吉凶。历法有效期两端分别报告实际求解器；详见深度审计与未解决原文分歧。

1.1.1 的 `chart/candidates.*.bearing_support` 保留各候选实际支持角区及全部 `mode_reasons`。`regions.from_degrees_exact/until_degrees_exact` 是有理数字符串，表示围绕已归一输入宅向展开的闭区间；例如跨北时可以出现负角度，它与加360°后的方位相同。多段角区可能支持同一个盘，不能因去重宅盘而丢掉理由；此时顶层 `mode_reason=multiple_supported_angle_regions`，实际理由逐段读取。X2只支持选定角区规则，闭端点及精确有理数运算是本系统的工程约定。

虚构示例 [4°±1°宅向支持](examples/fengshui-bearing-support.json) 返回唯一子向下卦，同时保留中央九度 `[3,9/2]` 与同宫同阴阳兼向 `[9/2,5]` 两段依据：

```bash
uv run --locked --extra dev fatebridge fengshui_xuankong_natal \
  --request-file docs/examples/fengshui-bearing-support.json \
  --fields layers.xuankong_natal.chart.bearing_support rulesets rule_trace --strict-fields
```

聚合年星仅出现在 `layers.annual_stars.palaces.*.annual_star_number`。住宅星与年度星不加总，当前九运不覆盖历史八运，未提供观察形势不产生综合吉凶。快照“玄空宅盘”和“年度飞星”是两个章节，导出注册表也分别识别。

原始中州运山向版本不包含其他门派替卦策略、玄空大卦、七星打劫、自动立极／纳气定向、月日时盘或峦头裁决。另可显式启用独立沈氏城门，其参考运、同元龙数字和水形条件单列，不改写历史宅盘。完整运山向数字盘不等于完整住宅勘察断法。

## 独立验证与复现

固定事实样本（本地数据：`../tests/fixtures/xuankong-reference.json`） 保留逐宫数字与出处，生产引擎不生成公开盘例预期值：

- X2的3套下卦：七运午子、八运甲庚、七运卯酉；4套替卦：八运甲庚兼寅申、七运午子兼丙壬、七运乾巽兼戌辰、七运卯酉兼甲庚。七套全部九宫27个数字吻合，包含五黄不替与替后仍按原阴阳飞布。
- Apache-2.0 [YuanZHAO321/FengShuiCalculators固定提交](https://github.com/YuanZHAO321/FengShuiCalculators/blob/2eacd85b9878452469c6669e7fff05d2c6226c97/docs/js/flyingstars.js) 独立生成9运×24山＝216套下卦，保存提交ID和两个文件SHA-256。168套无五黄的盘全部一致；含向五黄的24套也一致；192套吻合、24套山五黄不同。参考实现向五黄直接借物理向山阴阳，未采用本版本的借宅运追踪；这些盘的向山与宅运本宫恰互为相对山，元龙和阴阳相同，所以数值吻合不能证明其借法表述一致。
- 独立抄录X1同元龙山和阴阳表，以X2五黄规则、X3所载二／六／七运阴阳模式交叉核对，再展开48项固定五黄顺逆数字断言（24山盘、24向盘）；这些是独立阴阳表的规则验证，不冒称48幅出版盘图。未调用生产阴阳表或飞布函数生成预期值。
- 外部山五黄分支直接用 `!facing.yang`，相对本版本借宅运同元龙阴阳发生取反。保持原外部结果；[离线回归](../tests/fengshui/test_xuankong.py)核对固定夹具中的逐盘差异、元龙、借山、阴阳及逆向数列，不修改参考引擎强求216套一致，也不称其支持替星。

```bash
uv run --locked --extra dev pytest -q tests/fengshui/test_xuankong.py tests/fengshui/test_fengshui_surfaces.py
```

另覆盖9运24山正向及左右兼向共648组合、立春前后／跨时区、定运来源、五运、磁北要求、精确山界与角度误差、缺失输入、聚合层不互相覆盖及REST／实际MCP协议／CLI一致性。规则计算一致与现实预测有效性是不同验证范围。

沈氏整理本同版校勘另固定完整216条下卦种子与顺逆，213条与程序一致、3条保留差异；三处同版图中81数与程序一致，显示图文冲突，不能只归因于网页转录。未修改原文、切换版本或用三图通过认证整本，来源审计继续退出1。

后续完整盘图校勘覆盖全部216图5,832星数：215盘、5,831数吻合；七运申山寅向东宫山星的整理本与旧影印均印五，引擎为二。来源山星重复五、缺二，完整验收仍为false；故意把算法改为五虽然可使字面全合，却破坏九星完整性，不能获得整体通过。

领域回归、独立数值与原典参考、跨传输合同及真实模型咨询分别验证。规则计算一致不证明现实效果。

## 显式启用有限解释

在 `xuankong.interpretation`（聚合）或 `interpretation`（独立宅盘）传入独立评价运与证据，可启用 `xuankong_conditioned_v1@1.0.0`：有序山向星五行关系、当令星外部山水存在条件及床/门用途角色。默认不启用，既有宅盘数字和规则版本保持原合同。外局分宫独立确认，未确认、照片及边界候选保持缺失和候选状态；完整81组合断语与全宅勘察仍未覆盖。来源、读取字段和解释边界见[有限解释参考](../skills/onda-fengshui/references/xuankong-interpretation.md)，可复现示例见下节。

## 有限解释调用与复现

聚合布局入口仍为 `fengshui_assess`，选择 `xuankong_natal` 方法并启用 `analyze_layout`。在原宅盘请求的 `xuankong` 对象中追加：

```json
{
  "interpretation": {
    "ruleset_id": "xuankong_conditioned_v1",
    "current_period_number": 9,
    "period_evidence": "本次明确按九运评价，历史宅运另按原已确认事件保留",
    "external_forms": [
      {
        "direction": "N",
        "mountain_present": true,
        "water_present": false,
        "observation_basis": "user_confirmed",
        "evidence": "已确认全宅中心北宫外有山形、未见水形；距离与形态质量未鉴定"
      }
    ]
  }
}
```

示例只展示新增片段；完整请求仍需保留原先 `house`、历史 `period`、物件 `placements` 及用户证据。示例文字不能当作真实用户资料。磁北测量误差导致多个宅盘时，每个候选单独解读，不选择其中最有利的盘，也不合成确认结论。

完整虚构请求见[示例文件](examples/fengshui-xuankong-interpretation.json)，其中八运甲山庚向盘在九运评价时，西南当令山星的山形存在条件满足，东南当令向星的水形条件不满足；这两项条件不合成整体吉凶。可通过三个入口复现：

```bash
uv run --locked --extra dev fatebridge fengshui_assess --request-file docs/examples/fengshui-xuankong-interpretation.json
curl -X POST http://localhost:8010/api/fengshui/assess \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/fengshui-xuankong-interpretation.json
```

MCP 使用同一文件中的 JSON 调用 `fengshui_assess`。读取字段、状态语义和解释边界见 [skill 的有限解释参考](../skills/onda-fengshui/references/xuankong-interpretation.md#启用与读取)。

1.3.0的 `structure.classical_patterns` 计算反伏数式、逐宫历史运盘重叠、卷二28个下卦原例的有限数字对应及父母三般卦。规则、署名语境和原书校勘统一见[数字结构依据](../skills/onda-fengshui/references/classical-patterns.md)，不是完整七星打劫或现实预测认证。

## 主客生克的独立选择

在已有 `interpretation` 中加入 `"host_guest_ruleset_id": "shen_2011_host_guest_v1"`，可逐候选计算实际坐山宫与向首宫的地运、运山、运向及山向主客关系，每候选八条。向首宫以向星为主，运盘数字取该宫运星，不拿历史运数替代。旁六宫和中宫不扩用此规则；生入、生出与时令之生分开。

该层同时保留216条下卦的432个原文角色槽：422吻合、6在固定山向比较下不同、4字面未定，不逐例换基准配平，也不预断不同处都是笔误。来源、署名、可运行请求和解释校验见主客生克出入。这是盘层关系知识的增量，不是81对专门断语或全书吉凶认证。

## 王亭之基本时令的独立选择

在已有 `interpretation` 中加入 `"timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1"`，并按原合同提供评价时运与证据，可获得作者上卷第16–17页的基本旺生衰死，以及分别列出的先后天互用数字参考。字段为 `timeliness.*.author_classification`，作者与文件身份保留于 `timeliness_ruleset` 和顶层 `rulesets`。未选择时保留原先当令识别。

基本标签不表示房屋或人的成败，互用成员不表示现场可用。生气与互用星不会自动获得当令山水条件判断；历史宅盘、年度年星与候选盘保持各自依据。完整来源、九运表、反例与验证见[作者时令规则](../skills/onda-fengshui/references/wang-timeliness.md)。

作者子版本1.1.0另返回两条先后天图位推导，保留原表列示顺序与有向路径顺序。五运只列原表数字，评价运未知则不选择图位。基本时令、互用成员和图位须与实际候选星数一致，内部矛盾停止交付；固定释义不把数字相合解释为现场可用。

## 固定零正与五运分段

在已有 `interpretation` 中加入 `"fixed_lingzheng": {}`，按原合同明确评价运，即启用独立的 `shen_fixed_lingzheng_v1`。五运还需明确前／后十年及证据；未知时返回两组候选，不默认分段。固定零正与当前山向星分别列示，原有历史宅盘不变。

本分支区分高实、低洼与外部河流存在条件，不由无山推低洼，也不把一般水形或摆件当河流。详细输入、来源署名、字段和局限见[固定零正规则](../skills/onda-fengshui/references/fixed-lingzheng.md)。

## 可核验的固定中文释义

已有 `interpretation` 请求默认在顶层返回 `calculation_reading`，可用 `"include_calculation_reading": false` 关闭。每句保留精确目标路径与父候选、历史宅运、评价运、条件和来源，已请求的王氏时令、固定零正及城门分别解释；非当令、照片、未知和未覆盖不互相混用。

校验器要求完整原始响应及从可信执行端独立保管的同次完整回执，核对业务散列、回执、文字和上下文。它不验证任意模型改写或现实预测。字段、分页回读与命令见[固定释义参考](../skills/onda-fengshui/references/calculation-reading.md)。

## 逐候选的原书数表证据

数字宅盘默认返回 `source_comparison`，分别比较固定沈氏整理本下卦正文与盘图。它不改变起盘规则、星数、历史定运或候选；摘要在 `coverage.natal_source_comparison`，已知差异可在实际结果与快照中直接读取。原书值与计算值分开，替卦未覆盖不能当作相合。完整来源、生成命令和虚构调用见运行来源比较。
