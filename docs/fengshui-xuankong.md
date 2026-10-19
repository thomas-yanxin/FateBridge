# 玄空运山向宅盘：版本、输入和验证

[文档中心](README.md) · [风水总览](fengshui.md) · [请求示例](examples/README.md)

`fengshui_xuankong_natal` 的 REST 入口为 `POST /api/fengshui/xuankong_natal`，MCP 与 CLI 同名。选定版本 `xuankong_zhongzhou_v1@1.0.1` 完整计算九宫运星、山星、向星，支持下卦和中州派兼向替星。与 `layers.annual_stars` 独立；查询年份变化不改变历史宅盘。基础三法合同见[家居风水](fengshui.md)。

调用时先准备[历史定运与角度资料](#定运校验与角区实现)，再运行[三端示例](#三端调用)。已有数字盘需要进一步解释时，单独启用[有限解释](#显式启用有限解释)；维护者可从[独立验证](#独立验证与复现)追溯固定样本及版本分歧。

## 规则数据与版本维护

规则来源、选版差异、二十四山和替星表统一维护在 [skill 的历史宅盘参考](../skills/onda-fengshui/references/xuankong.md)。

生产规则为离线 [xuankong-v1.json](../src/fatebridge/data/fengshui/xuankong-v1.json)，与基础规则数据及其版本分别维护。规则语义变化须另建版本及独立样本；1.0.1 修复既定角区的浮点实现与不确定输入处理，五黄和替星表未改。

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
  "bearing_uncertainty_degrees": 0,
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

1.0.1改为闭角区与测量闭区间的直接相交判断，不扩张浮点容差。所有24山的±4.5°、±7.5°均验证分界及两侧最近可表示浮点数；区间端点碰线也保留双侧候选。给定 `house.sitting_trigram` 时，用已确认坐卦约束候选宫位，避免跨宫误差盘与八宅已确认坐卦冲突；同宫内两山或下／替模式的歧义仍保留。

## 输出分层与计算过程

`layers.xuankong_natal` 包含历史定运、住宅ID、测量依据与误差、24山表、唯一 `chart` 或多个 `candidates`。每盘都有独立 `period_chart`、`mountain_chart`、`facing_chart`，九宫 `palaces` 分别返回固定 `palace_number` 与三个星数；固定宫数不可当成运星。

`trace.mountain`、`trace.facing` 保留原入中星、借用的原星／宅运、同元龙山、阴阳、顺逆、最终入中星、是否发生数值替换与五黄政策。宫位飞行路径是 `C,NW,W,NE,S,N,SW,E,SE`；运盘始终顺飞，山向盘按各自原元龙阴阳顺逆。

聚合年星仅出现在 `layers.annual_stars.palaces.*.annual_star_number`。住宅星与年度星不加总，当前九运不覆盖历史八运，未提供观察形势不产生综合吉凶。快照“玄空宅盘”和“年度飞星”是两个章节，导出注册表也分别识别。

当前版本不包含其他门派替卦策略、玄空大卦、城门、七星打劫、自动立极／纳气定向、月日时盘或峦头裁决。完整运山向数字盘不等于完整住宅勘察断法。

## 独立验证与复现

[固定事实样本](../tests/fixtures/xuankong-reference.json) 保留逐宫数字与出处，生产引擎不生成公开盘例预期值：

- X2的3套下卦：七运午子、八运甲庚、七运卯酉；4套替卦：八运甲庚兼寅申、七运午子兼丙壬、七运乾巽兼戌辰、七运卯酉兼甲庚。七套全部九宫27个数字吻合，包含五黄不替与替后仍按原阴阳飞布。
- Apache-2.0 [YuanZHAO321/FengShuiCalculators固定提交](https://github.com/YuanZHAO321/FengShuiCalculators/blob/2eacd85b9878452469c6669e7fff05d2c6226c97/docs/js/flyingstars.js) 独立生成9运×24山＝216套下卦，保存提交ID和两个文件SHA-256。168套无五黄的盘全部一致；含向五黄的24套也一致；192套吻合、24套山五黄不同。参考实现向五黄直接借物理向山阴阳，未采用本版本的借宅运追踪；这些盘的向山与宅运本宫恰互为相对山，元龙和阴阳相同，所以数值吻合不能证明其借法表述一致。
- 独立抄录X1同元龙山和阴阳表，以X2五黄规则、X3所载二／六／七运阴阳模式交叉核对，再展开48项固定五黄顺逆数字断言（24山盘、24向盘）；这些是独立阴阳表的规则验证，不冒称48幅出版盘图。未调用生产阴阳表或飞布函数生成预期值。
- 外部山五黄分支直接用 `!facing.yang`，相对本版本借宅运同元龙阴阳发生取反。保持原外部结果；[离线回归](../tests/test_xuankong.py)核对固定夹具中的逐盘差异、元龙、借山、阴阳及逆向数列，不修改参考引擎强求216套一致，也不称其支持替星。

```bash
uv run --locked --extra dev pytest -q tests/test_xuankong.py tests/test_fengshui_surfaces.py
```

另覆盖9运24山正向及左右兼向共648组合、立春前后／跨时区、定运来源、五运、磁北要求、精确山界与角度误差、缺失输入、聚合层不互相覆盖及REST／实际MCP协议／CLI一致性。规则计算一致与现实预测有效性是不同验证范围。

领域回归、跨传输合同、Linux golden 与真实模型咨询分别验证。可在对应环境运行 `scripts/audit_linux_golden.py`；环境不匹配时不得伪造平台或跳过差异来声称通过。规则计算一致不证明现实效果。

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
