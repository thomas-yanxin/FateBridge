# 家居风水基础计算

[文档中心](README.md) · [请求示例](examples/README.md) · [玄空宅盘](fengshui-xuankong.md) · [咨询技能](../skills/onda-fengshui/SKILL.md)

当前提供七个工具：公共方位、个人命卦、八宅、金锁玉关基础砂水、年度紫白飞星、玄空历史宅盘和分层合参。三端来自同一目录，核心规则离线计算，不依赖外部风水服务。布局、室内关系、材质及候选方案通过 `fengshui_assess` 的独立分支审查。结果表示选定传统规则中的关系；规则来源、计算一致性和现实预测效力是不同事项。

本项目采用的专家访谈口径以九宫飞星、金锁玉关和八宅为主要方法；局部工位／合租先考虑飞星、次金锁，八宅命卦独立处理。政策是用户提供的专家口径，来源、方法细节及环境上下文各自有版本；不将本人或周围人的八字／紫微喜忌代入房屋五行。现代 BTB 仅用户明确另选时作为作者辅助，不作默认替代。

| 你要完成什么 | 从哪里开始 |
| --- | --- |
| 运行一个请求 | [入口与最小输入](#入口与最小输入)、[三端例子](#三端例子) |
| 区分个人命卦、宅盘与年盘 | [规则与版本](#规则与版本)、[输入语义和边界](#输入语义和边界) |
| 关联门床桌灶或比较候选 | [布局对象](#布局对象的通用计算)、[候选布局合同](../skills/onda-fengshui/references/scene-planning.md) |
| 判断结果是否完整、是否可以执行 | [分层结果与覆盖状态](#分层结果与覆盖状态) |
| 维护实现与验收 | [实现与规则数据](#实现与规则数据)、[验证与维护](#验证与维护) |

## 入口与最小输入

| REST POST | MCP / CLI | 输入 | 输出层 |
| --- | --- | --- | --- |
| `/api/fengshui/directions` | `fengshui_directions` | 可选 `bearing_degrees` 和 `north_reference` | 固定八方、宫数；角度对应的八方与24山索引 |
| `/api/fengshui/minggua` | `fengshui_minggua` | 公历 `birth_date`、`effective_birth_year` 或含时区的 `birth_at` 三选一；`gender_convention` | 命卦、原始数、寄宫、东西组、个人八方关系 |
| `/api/fengshui/bazhai` | `fengshui_bazhai` | `house`、`occupants`；可选 `placements` | 坐山宅盘、逐人命盘、位置与朝向的用途判断 |
| `/api/fengshui/jinsuo` | `fengshui_jinsuo` | `features` | 八宫砂水偏好、逐个观察判定 |
| `/api/fengshui/annual_stars` | `fengshui_annual_stars` | `effective_year` 或含时区的 `query_at` | 当年入中星、九宫年星、立春有效期、当前元运 |
| `/api/fengshui/xuankong_natal` | `fengshui_xuankong_natal` | `house`、历史 `period`，按需提供测量误差及 `interpretation` | 运／山／向盘、下卦／替星与分界候选；有限解释须显式启用 |
| `/api/fengshui/assess` | `fengshui_assess` | 已确认的住宅、住户、环境、年度或历史宅运输入；可选 `methods`、`scene`，布局时 `analyze_layout=true` | `bazhai` / `jinsuo` / `annual_stars` / `xuankong_natal` 独立分层；布局及所请求补充审查 |

可运行输入按用途列于[示例索引](examples/README.md)。完整约束见 `/openapi.json`、MCP `tools/list` 和 `fatebridge describe fengshui_assess`。新 family 是 `fengshui`；不加入个人 `analyze_destiny` 或 `profile` 默认系统。

`fengshui_xuankong_natal` 提供中州派完整运／山／向数字盘与兼向替星；聚合时显式选择 `xuankong_natal`，与年度飞星独立。定运资料、分界候选、规则版本及独立盘例见 [玄空宅盘](fengshui-xuankong.md)。

按问题展开的资料入口：基础[规则来源](../skills/onda-fengshui/references/rule-sources.md)、[布局形态](../skills/onda-fengshui/references/layout-rules.md)、[场景与候选比较](../skills/onda-fengshui/references/scene-planning.md)、[室内关系及材质器形](../skills/onda-fengshui/references/sourced-interior-rules.md)、[玄空有限解释](../skills/onda-fengshui/references/xuankong-interpretation.md)。[BTB 桌面作者规则](../skills/onda-fengshui/references/surface-rules.md)仅在用户明确另选时使用，不作为无方位的默认替代。

## 三端例子

先按[快速入门](getting-started.md)安装项目。以下命令在仓库根目录执行，REST 示例要求本地服务已启动；API Key 请求头按服务配置提供。

将以下虚构输入保存为 `home.json`，用于查看原始分层结果；它没有启用家具布局分析。仓库另提供含布局对象的 [完整示例文件](examples/fengshui-home.json)。示例的年份、方向和人物均须按现场事实替换。

```json
{
  "house": {
    "object_id": "home",
    "facing_degrees": 180,
    "north_reference": "magnetic",
    "orientation_basis": "measured"
  },
  "occupants": [
    {"subject_id": "a", "effective_birth_year": 1990, "gender_convention": "male"},
    {"subject_id": "b", "effective_birth_year": 1990, "gender_convention": "female"}
  ],
  "features": [
    {
      "object_id": "pond",
      "direction": "S",
      "classification": "water",
      "classification_basis": "user_confirmed",
      "evidence": "已确认南方为水体"
    }
  ],
  "effective_year": 2026
}
```

```bash
# REST：API Key 鉴权按服务配置额外提供请求头。
curl -X POST http://localhost:8010/api/fengshui/assess \
  -H 'Content-Type: application/json' --data-binary @home.json

# CLI：完整 JSON 请求，适用于住宅、住户和环境嵌套对象。
uv run --locked --extra dev fatebridge fengshui_assess --request-file home.json --compact

# 简单工具也支持普通参数。
uv run --locked --extra dev fatebridge fengshui_minggua --effective-birth-year 1990 --gender-convention female
uv run --locked --extra dev fatebridge fengshui_annual_stars --query-at '2026-02-04T04:03:00+08:00'

# 复杂字段可用 JSON 参数；显式字段覆盖请求文件同名顶层字段。
uv run --locked --extra dev fatebridge fengshui_assess --request-file home.json \
  --methods '["annual_stars"]' --effective-year 2027
```

```python
import asyncio
import json
from pathlib import Path
from fastmcp import Client

async def main():
    async with Client({"mcpServers": {"fatebridge": {
        "command": "uv", "args": ["run", "--locked", "--extra", "dev", "fatebridge-mcp"]
    }}}) as client:
        inputs = json.loads(Path("home.json").read_text())
        result = await client.call_tool("fengshui_assess", inputs, raise_on_error=False)
        print(result.is_error, result.structured_content)

asyncio.run(main())
```

`--request-file` 当前由七个风水工具明确启用，接受 JSON 对象，未知字段照常报错；不是只挑出生字段的 `--subject-file`。合并优先级为模型默认值 < subject 档案 < request 文件 < 显式字段参数。嵌套字段整体替换，不做递归混合。请求文件解析失败退出2，模型校验失败退出1，合法 `partial` 退出0。

## 规则与版本

规则数据位于 `src/fatebridge/data/fengshui/rules-v1.json`，随 wheel 打包。四个规则集当前均为 `1.0.0`，每个输出层含 `ruleset_id`、`version`、`bundle_version`、来源标题／URL／类别／适用范围与约定。逐项关系带 `rule_id` 和 `source_ids`，不能只在最终文本附一条笼统来源。

| 规则集 | 精确范围 | 来源与约定 |
| --- | --- | --- |
| `houtian_directions_v1` | 后天八卦、固定宫数、八方角区、24山索引 | 《沈氏玄空学》转录；0°北、顺时针；左闭右开 |
| `bazhai_sitting_v1` | 坐山起伏位；1864命卦锚点；8×8大游年；明确用途约定 | 《八宅明镜》上下卷转录、书目及现代三元纪元；默认命卦立春换年，可明确选 `january_1` |
| `jinsuo_basic_fixed_v1` | 一二三四砂、六七八九水；逐个确认观察 | 署名陈益峰《九砂九水》注解所引传本；转载及底本归属限制明确登记 |
| `annual_zibai_lichun_v1` | 年度紫白入中、顺飞九宫、立春区间、当前20年元运 | 《沈氏玄空学》转录、Joey Yap 2026年盘、作者立春约定与香港天文台年历 |

详见[基础规则与来源](../skills/onda-fengshui/references/rule-sources.md)。未知规则 ID 拒绝；改变纪元、换年、坐山起法或砂水规则时，应新增规则版本与独立样本，不能静默替换原版本。`january_1` 是命卦中显式可选的现代计算约定，不宣称所有《八宅明镜》古本都按立春换年。

定义 `wrap9(n) = (n - 1) % 9 + 1`，有效年为 Y：

- 男命原始宫数 `wrap9(1 - (Y - 1864))`；女命 `wrap9(5 + (Y - 1864))`。原始五数在计算完成后分别寄坤二、艮八，输出保留原始数与替换信息。
- 两卦三爻从初爻开始编码为 bit0/1/2；异或0至7分别对应伏位、祸害、绝命、天医、生气、六煞、五鬼、延年。
- 年星入中 `wrap9(1 - (Y - 1864))`；路径 `C,NW,W,NE,S,N,SW,E,SE` 逐宫递增。年际入中递减与同年顺飞不同。

## 输入语义和边界

工位／合租／家居可传 `scene=workstation|shared_rental|home`；未显式传方法时按已有事实选层，独立形态/桌面不再自动引入无关三法。局部优先顺序只组织核对和说明，不补历史定运、年份或方位。家具动作许可与独立候选方案分别用 `layout_constraints` / `layout_alternatives`，详见[场景选法与候选布局合同](../skills/onda-fengshui/references/scene-planning.md)。候选重算现有规则、不继承旧形态、不平均评分；完整古典形势、独立阳宅三要结构、三合/大卦及完整玄空组合解释仍明确未覆盖。

`method_policy.priority_review_status` 与每法 `not_selected_reason` 单独报告优先审查范围，区分自动缺输入和显式排除；不改变已选方法的计算完成状态，也不把未选方法算成已审。局部所需飞星／金锁缺资料时保留范围，不为了 complete 补事实；用户排除或仅问其他已选范围时不强追资料。

### 方位与分宫

角度范围0–360，360归零；八方中心间隔45°，半宽22.5°；24山中心间隔15°，半宽7.5°。正好22.5°归东北／丑山。宅向推导坐山时加180°；同时提供 `sitting_trigram` 必须一致。基础方位／八宅角度必须声明 `north_reference=magnetic|true`（玄空当前版本要求 magnetic），不自动校正磁偏角。只有已确认宅卦时可直接提供 `sitting_trigram`。

`house.division_method` 只接受 `confirmed_angular_sectors`。八方角区、九等分网格和示意九宫图不是同一个几何计算；当前不自动识别户型图片、不自动定中心，也不推断不规则户型分宫。

### 环境与实际使用范围

`environmental_context` 可独立保存方位／图纸对齐与中心确认、同住家庭辈分／排行、独立确认生肖、各楼层／院落与明确形态观察；不要求为这些事实提交生辰。输出位于 `layout_analysis.environmental_context`，其中上下文宫位绑定须经过方向、户型对齐与立极三个门槛。该模块不计算飞星，也不把家庭象征索引当成现实人物受影响结论。院落归第一层但共享整体关系仍需复核；局限本层且异层适宜有依据时，不自动将该局部不利归给异层住户。厨卫、材质和器形事实不自动变成禁忌，未有具体判据的项目保留未覆盖。具体字段以当前输入 Schema 为准，核对流程见[风水咨询闭环](../skills/onda-fengshui/references/consultation.md)。

仅解释家庭卦名／对宫用 `household_scope=symbolic_reference`，不绑定真实方向或为此追罗盘；默认 `environmental_binding` 才关联环境方区。家庭及生肖输出的 `scope`／适用方法限定为飞星、金锁的环境象征索引，不作为八宅命卦；实际个人匹配看八宅层。

无方位具体关系新增 `environmental_context.interior_relations`：以源／目标对象及明确角色检查本次有来源的厨卫、床灶、镜面、梁管和尖角关系；床位尖角规则限实体柱角，床头／灶背共墙须确认墙另一侧实际便器，旧四类粗粒度 `observations` 不自动触发更强规则。`material_facts` 另存材质、器形、颜色与明确代表物资格问题。实际提供对应输入才返回 `layout_analysis.interior_analysis/material_analysis`；关系 null 和照片均待确认，确认 false 只说明本条不成立。资格不确认摆位或 ready，作者来源、条件工程动作和镜面方法异议分列，详见[本轮有来源规则](../skills/onda-fengshui/references/sourced-interior-rules.md)。

多层及独立院落还须各自确认 `floors[].floorplan_alignment_confirmed`、`center_confirmed`，并以 `uses_shared_orientation=true` 采用全宅已确认方向；全宅中心不自动成为每层中心。逐层门槛不足时不能提交关联对象的物理落宫事实。当前各层复用本次已明确声明的宅／年盘，位置按各自确认中心提供；不会自动建立每层宅运或自动立极。

`floors[].subject_ids` 是正向使用名单，省略不等于无人或某人不使用。仅在需要作负向排除时，相关作用空间完整使用范围须以 `usage_confirmed=true` 与成对 `usage_evidence` 明确确认；否则保持待确认，不能据其他适宜层的住户名单自动豁免本层／共享影响。

### 出生日期与查询时间

时间输入必须含 UTC 偏移或Z，`timezone_name` 默认为 `Asia/Shanghai`，可用 IANA 名称或偏移。每个出生／查询时刻与对应有效年字段二选一。显式有效生年表示调用方已确认换年，无需出生小时或真太阳时。未知 `gender_convention` 应省略或传 null，返回男女候选并标记 `partial`，不会默认男性。支持有效年1800–2199、带时区输入1801–2199；区间结束可延伸下一年。

命卦另接受公历 `birth_date`，与有效生年、出生时刻三选一。按所选时区计算立春所在日期；之前取上一有效生年，之后取本年，立春当日保留 `partial` 并要求出生时刻。选择 `january_1` 时日期即可确定生年。该路径不构造虚假的出生小时，也不使用真太阳时。

年盘有效期是 `[立春, 下次立春)`，不硬编码2月4日午夜，也不按春节。节气沿用现有 `almanac`：优先 Swiss，可能回退线性近似；输出 `timing` 说明供应函数、Swiss可用性、可能回退及独立核验范围。登记的外部参考核对2026立春日期和分钟，不认证现有引擎的秒级精度。

### 物件位置与朝向

布局对象分别提供 `location_direction` 与可选 `facing_direction`。后者必须配套用途语义：门 `door_facing`、床头 `headboard`、书桌 `desk_facing`、灶 `fire_mouth`。灶座按凶方约定、已确认火门按吉方约定；现代燃气旋钮不是自动等同古火门。床头与书桌朝向是本版本明确的应用约定。住宅宅盘与每位住户命盘分别输出；`subject_id` 只筛选一位布局关联住户，`subject_ids` 选择明确的多人使用集合，两者互斥；不传二者则保留应用全部已提供住户的语义，均不修改宅卦。多人列表非空、成员唯一且必须引用已提供住户。对象实际使用者与全宅住户分开，不能把同住自动当共用。未知住户引用、重复住户／布局 ID 被拒绝。

位置和朝向至少提供一项。只知道朝向时仍计算该朝向的宅／人关系，位置缺失明确返回 `partial`；朝向不会填进位置，也不会用来推测住宅坐向。

## 布局对象的通用计算

在现有 `fengshui_assess` 请求中设置 `analyze_layout=true`，输出 `layout_analysis`；不增加工位或其他场景专用接口。它对门、床、桌、灶复用同一套盘和用途规则：

- `placement_findings`：对象的位置分别关联年星和玄空宅盘；玄空候选盘、运／山／向三角色保留。八宅位置和朝向分别返回。
- `adjustment_options`：从当前判定使用的同一规则反算匹配方位。按宅及各住户分列，只有已确认作用域参与交集；没有共同匹配方向时保留差异，不择一覆盖。灶座与火门采用相反的用途偏好。
- `environment_adjustments`：已确认砂水特征的保留／调整分类；未知分类不生成目标分类。水壶、镜子或小摆件不能自动替代已确认环境砂水。
- `element_relationships`：分别计算每个已关联星五行的生、同、泄、克与被克关系。复用共享五行图；例如火由木生、泄到土、被水克。星五行不是住户喜用神，这些关系不证明具体物件、颜色或材质有化煞效果。
- `layout_analysis.status`：本次布局关联计算的完成状态；独立于顶层原始盘 `status`。年盘已算完而对象位置未知时，原始盘可以 `complete`，布局关联保持 `partial`。
- `layout_analysis.analysis_progress` 与 `coverage.analysis_progress`：保留原 status，另分计算完整性、所选规则审查及候选动作可执行性。已确认没有独立规则的物件可结束审查；属性 unknown 或照片候选仍需事实确认。可选新增不变成必做任务，blocked 不再追其执行条件，方向关系未验证搬转可行性时不返回 ready。计数单位与 pending_confirmations 的用途随结果明确，不能把输出确认路径当请求参数。
- 普通解释独立读取 `analysis_progress.interpretation_status`：`available` 有确认判断或参考可解释，`conditional` 有实际候选观察可条件式解释，`scope_only` 仅说明已知覆盖限制，`insufficient_evidence` 尚无事实依据。partial、候选或动作未 ready 不阻塞已有依据。`follow_up.conclusion_candidates` 是按当前问题择要追问的候选，`execution_only` 只约束动作落实；不把二者拼成必补清单。未实现能力直接说明，不继续索取无法补足能力的资料。
- `follow_up` 两类列表引用同一结果中 `pending_confirmations.path`，不重复确认记录，也不是新输入参数。一个路径同时用于事实判断与动作时只列在结论候选中；具体理由及动作范围仍查原确认记录。

同一请求包含多件家具时，可分别关联实际使用人。例如住户甲、乙共用床，丙只用书桌，床可传 `subject_ids=["a", "b"]`，桌传 `subject_id="c"`。床的逐人判定和共同匹配方向仅由甲乙派生；加入丙的资料不会改变这张床的结果。住宅宅盘若已提供，仍单独参与该对象判断，不因使用人筛选而消失。更正使用者时替换集合后重新计算，不沿用旧共同方向。

示例：只知道某人的桌朝西，尚不知道房屋坐向及桌子所在宫位：

```json
{
  "methods": ["bazhai"],
  "analyze_layout": true,
  "occupants": [{"subject_id": "a", "birth_date": "2000-12-10", "gender_convention": "male"}],
  "placements": [{"object_id": "table", "purpose": "desk", "subject_id": "a", "facing_direction": "W", "facing_role": "desk_facing"}]
}
```

该请求直接给出离命西向五鬼及个人匹配方向 N/E/SE/S，保留宅向和位置缺失，不强制补出生分钟。若加入年盘或宅盘，必须补对象的位置才能关联相应落宫；面朝西不能证明对象位于西宫。

室内入口视野、入口直线与实体背靠另按明确作者版本计算；有条件的元素代表物和2026年度候选规则见下节。完整峦头、距离吉凶阈值、搬动几何可行性和具体物件效果大小仍列在 `unsupported_queries`，不会以生活常识或虚构阈值填补。

## 室内形态与有条件物件规则

同一 `fengshui_assess` 接受三个可选输入，提供这些输入即启用布局计算，不必另外开启新工具：

| 输入 | 输出 | 限定范围 |
| --- | --- | --- |
| `form_observations` | `layout_analysis.form_analysis` | 现代作者室内控制位置：入口可见、避开入口直线；床/桌加实体背靠。独立分析可 `methods=[]`，无需生辰或宅向 |
| `element_adjustments` | `layout_analysis.element_remedies` | 绑定已计算对象、方法与明确生/泄目标，再按 AFSI 作者版本给代表物/颜色；不由命卦推断喜用神 |
| `annual_remedy_ruleset_id=pang_2026_annual_v1` | `layout_analysis.annual_remedies` | 显式选取作者2026年盘南5/西北2的金元素候选及避火；只按对象所在宫位，不按朝向或其他年份 |

形态的 `observation_basis` 为 `measured`、`user_confirmed` 或 `image_observed`。照片仅为候选，不能提供米数；实际距离须测量/用户确认。未知视野、直线和背靠省略，不转成 false。右后门仅说明在使用者后半空间，不能证明直线冲，也不能投影成住宅某宫。1.5米等距离只记录，来源没有统一吉凶阈值。镜面只作为确认能补入口视野的条件选项，不作为通用化煞物。

元素目标的 `target_method` 必须已选中，且 `object_id` 必须引用已提供布局对象。八宅还须指定 `subject_id`、`aspect`；玄空须指定运/山/向 `star_role`。候选命卦/候选宅盘只给候选方案，不能输出确认处方。灶座的凶方特殊用途不能套用普通凶星削弱。本版本优先列实际元素代表物，再列色彩替代，不要求购买、数量、重量或效果概率。

方案同时返回 `cross_scope_effects`，显示加入的元素对同一对象其他已算层的生/泄/克关系；这些关系不合成一个“全宅有利”结论。`supplemental_rulesets` 和顶层 `rulesets`/`rule_trace` 保留作者、版本、原文位置和检索 SHA-256；`supplement_statuses` 区分未请求、完成、部分及年份不支持。不同作者对物件路线的分歧在 `method_disagreements` 明示。

可运行示例见 [形态输入](examples/fengshui-forms.json)、[元素目标](examples/fengshui-elements.json) 和 [年度作者候选](examples/fengshui-annual-remedy.json)。来源核对、采用与排除的规则见[形态与元素规则证据](../skills/onda-fengshui/references/layout-rules.md)。

环境特征要求方位、`classification=sand|water|mixed|unknown`、`classification_basis=measured|user_confirmed` 与非空 `evidence`。标签不参与分类；道路、镜子、高楼、缺水都不能自动推导砂水。`mixed`／`unknown` 返回 `undetermined` 和缺失项，不给吉凶。

## 分层结果与覆盖状态

先检查协议成功与否，再看原始盘、布局及具体请求分支的状态。最后分别核对规则覆盖、未选方法与动作可行性；这些状态回答不同问题，不能只读顶层 `status`。通用区别见[结果状态](concepts.md#状态与覆盖分开阅读)。

实际结果的主字段：

```text
status: complete | partial
layers.bazhai: house.sectors / occupants[].candidates[].sectors / placement_findings
layers.jinsuo: preferences / feature_findings
layers.annual_stars: palaces / effective_year / time_context / current_period
layers.xuankong_natal: 历史宅运、运／山／向盘及边界候选（显式选择时）
method_policy / method_details: 选法口径、实际层次、固定宫与星五行及带来源象意参考
layout_analysis.environmental_context: 方位门槛、家庭/生肖关注、多层范围、现代设计及未覆盖观察
layout_analysis.interior_analysis: 实际提供双对象关系后的有限作者判据、异议及条件动作
layout_analysis.material_analysis: 实际属性、器形参考与明确代表物用途的有限资格
rulesets / rule_trace: 各层规则版本、来源及范围
coverage: implemented_layers / missing_inputs / unavailable_layers / not_requested_layers
conflicts: 逐人方向差异、宅与人作用域差异、三层叠加清单
snapshot_text / snapshot_export: 同一组计算事实的分层可读快照
run_metadata: 三端通用运行元数据
```

示例中，坎宅南方为延年，金锁玉关南方基础偏水，2026南宫年星为五黄；三项条件分别返回，`distinct_scope_overlay` 表示不同作用域并置，不表示已经证明三法矛盾。1990男女两位住户的北方分别为伏位与五鬼，产生 `personal_direction_difference`，不会自动以户主或男性覆盖另一人。未知男女候选不能被当成两个真实住户制造冲突。

`complete` 仅表示请求的基础层已有所需输入，不代表全流派、完整环境勘测或进阶宅盘完成。八宅缺住户时宅盘仍可计算，但个人层缺失使状态为 `partial`；金锁玉关只覆盖提供的特征，不保证全宅环境已勘测。空请求返回各层缺失项，HTTP200／MCP成功／CLI退出0。非法输入返回校验错误，HTTP422／MCP `isError=true`／CLI退出1。`methods` 可以只选择需要的层，未请求的层不计算。

八宅游年星与年度紫白星有不同名称空间，例如八宅生气贪狼属木、一白贪狼属水。`palace_number` 始终是固定宫数，`annual_star_number` 才是当年临宫星数；`current_period` 是当前日历元运，不是住宅建造元运。

`method_details.status=reference_only` 表示方法与象意参考。按 `mapping_boundaries` 区分固定宫 `palaces`、实际临宫星数 `flying_star_references`、八宅游年星名 `bazhai_you_nian_references`，不能因同名混用五行。跨文本本卦人物／器物、Joey Yap 一至九星主题与有限职业例分别保留来源及条件；未覆盖职业不补造。`object_observation_references`、各法 `application_references`、砂水 `form_condition_references` 和 `material_shape_reference` 补观察与用途说明，不构成自动分类、摆放处方或职业预测。精确字段以实际返回的 `method_details` 为准，来源及剩余边界见[方法补充说明](../skills/onda-fengshui/references/sourced-interior-rules.md#与方法细节的区别)。

本版明确未实现：月飞星、金锁24山及形态／距离／元运组合、自动户型几何。24山角度索引可用不表示这些24山论断可用。没有三法总分，也不生成疾病、死亡或财富断语。

可用通用 `fields` 投影及快照开关降低体积：

```bash
uv run --locked --extra dev fatebridge fengshui_assess --request-file home.json \
  --fields layers.annual_stars.palaces.S coverage --no-include-snapshot-text --compact
```

快照包含实际方向、命卦、砂水观察、年星、差异和来源。风水请求不接受 `selected_sections`；`snapshot_export` 记录本次实际生成的分层 section，进一步裁剪用 `fields`。

## 验证与维护

```bash
uv run --locked --extra dev pytest -q tests/test_fengshui.py tests/test_fengshui_surfaces.py
```

离线测试用[固定参考事实](../tests/fixtures/fengshui-reference.json)登记的提交／SHA-256核对1900–2099男女命卦400项、独立八宅字典64项，并测试纪元／世纪／五数寄宫、立春前后与时区等价、方位边界、坐向反转、门床灶用途、不同住户、未知／混合砂水、来源版本、三端真实调用／校验／投影／请求文件。2026九宫另用作者出版年盘核对。代表性输入加入现有全端与 golden 覆盖，新增快照不重写旧工具数值基线。

外部参考 [JackieL233/fengshui-master 固定提交](https://github.com/JackieL233/fengshui-master/blob/2666304c5cb4ac13091c8c1fcdd4e40c218b275a/fengshui-master/scripts/minggua.py) 仅核对有效生年和八宅关系，不覆盖精确出生时间、年飞星、金锁玉关或完整玄空。金锁玉关未登记独立引擎比较；其验收依据为明确登记的八宫传本规则与输入语义检查。

## 场景兼容与归一化

公开Schema用 `methods=null` 表示自动选法。MCP会物化参数默认值，因此不能发布旧三法列表为默认、再试图区分字段是否省略；null与省略在三个传输中采用相同路径，内部归一为实际方法列表。`coverage.scene_scope.selection_policy`说明选法策略，不把传输归一化后的字段错误标记为用户原始选择。

未传场景且未传方法的独立形态/桌面请求同样按事实选层，不再强制补充三法资料。其余无场景旧请求保留原先八宅/金锁/年星默认，原始计算与 golden 基线保持兼容。

## 实现与规则数据

领域模块位于 `src/fatebridge/core/fengshui/`，分别处理方向、历法、八宅、年星、历史宅盘、环境上下文、室内关系、材料资格与候选重核。`services/fengshui.py` 编排独立层，`data/fengshui/` 保存实际版本和来源；这些空间规则不并入个人八字／紫微评分。

公共卦名、五行生克和节气函数可以复用，各方法的星名、五行、作用域和解释规则仍独立。导出类型、快照标题或工具调用成功不能代替实际计算覆盖。

当前输入、输出与支持范围以共享 Schema 和本页[入口表](#入口与最小输入)为准；复杂 CLI 输入使用公开 `--request-file`，不将整个户型塞进绕过校验的字符串或个人 `--subject-file`。

## 调用与状态合同

布局主入口为 `fengshui_assess`，独立入口包括 `fengshui_directions`、`fengshui_minggua`、`fengshui_bazhai`、`fengshui_jinsuo`、`fengshui_annual_stars` 和 `fengshui_xuankong_natal`。按问题选择所需层，不为凑齐方法补出生、方位或宅运。

请求拒绝未知规则版本及无效枚举；未知朝向、未知起算法或未知砂水不得静默转成默认吉凶。有效但资料不足时保留 `partial`；不合法输入走校验错误。计算状态、规则覆盖、方法优先审查和动作可执行性分别报告。

实际 `rulesets`、`rule_trace` 和分层结果保留来源、版本、对象、使用人、位置／朝向、事实依据及不确定性；其完整形状由当前输出合同定义，不使用过时设计示意充当运行结果。首轮字段与咨询闭环见[场景技能](../skills/onda-fengshui/SKILL.md)，候选独立事实和许可见[候选布局合同](../skills/onda-fengshui/references/scene-planning.md)。


## 补充规则的验证

### 室内形态、元素与年度作者规则

规则来源证明这里采用的传统/作者约定；跨传输测试证明同一输入的一致计算；二者都不证明现实预测效力。回归覆盖无生辰的独立形态、门冲误判、距离不造阈值、镜面条件、灶座例外、候选盘、调节目标、年份/立春边界、跨作用域关系以及REST/MCP/CLI校验和投影。Linux/Python3.12 golden与真实模型对话须另外验收。

### 桌面作者规则

期待值先从来源独立规定；回归变换目标、九个起始区域、生日/朝向、ID/标签、未知/照片、固定物件和禁止动作。生产代码和测试不包含用户生日/照片或预设用户回答。允许blocked和无规则结果，不按建议数量、关键词或必须摆成某位置奖励。

用户案例用于现场回放，不能替代跨变体回归。真实模型体验、结构化调用、三端一致、Linux golden各自报告；规则来源和软件一致性不证明传统效力。

## 工位活动、隔挡与材料条件

书桌工作／学习用途、入口隔挡与材料施用条件沿用 `fengshui_assess` 的共享请求模型，详细字段、来源与边界见[工位作者规则](../skills/onda-fengshui/references/workstation-authored.md)。可运行虚构请求：[玄空活动](examples/fengshui-workstation-activity.json)、[入口隔挡](examples/fengshui-entry-barrier.json)、[材料条件](examples/fengshui-material-application.json)。REST、MCP、CLI 使用同一嵌套输入，严格投影按需追加 `layout_analysis.workstation_analysis` 或 `layout_analysis.material_analysis`。WOFS 非 BTB 桌面摆放仅为作者参考，未启用固定吉位判定。
