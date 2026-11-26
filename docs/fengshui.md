# 家居风水计算参考

[文档中心](README.md) · [请求示例](examples/README.md) · [现场资料与来源](interpretation/fengshui/consultation.md)

FateBridge 提供八个离线风水计算工具，覆盖公共方位、个人命卦、八宅、金锁玉关基础砂水、年度紫白、十二节月紫白、中州派玄空历史宅盘与分层合参。各方法规则版本与来源分别保留，不合并成单一总分，现场资料核对流程见[风水咨询参考](interpretation/fengshui/consultation.md)。

## 入口与最小输入

| REST POST | MCP / CLI | 输入重点 | 输出层 |
| --- | --- | --- | --- |
| `/api/fengshui/directions` | `fengshui_directions` | 可选 `bearing_degrees` 与 `north_reference` | 固定八方、洛书宫数与 24 山角区索引 |
| `/api/fengshui/minggua` | `fengshui_minggua` | `birth_date`、`effective_birth_year` 或 `birth_at` 三选一；`gender_convention` | 命卦、寄宫、东西组与个人八方关系 |
| `/api/fengshui/bazhai` | `fengshui_bazhai` | `house`、`occupants`；可选 `placements` | 坐山宅盘、逐人命盘与位置/朝向用途判断 |
| `/api/fengshui/jinsuo` | `fengshui_jinsuo` | `features`（方位、砂水分类与确认依据） | 八宫砂水偏好与逐个观察判定 |
| `/api/fengshui/annual-stars` | `fengshui_annual_stars` | `effective_year` 或含时区的 `query_at` | 入中星、九宫年星、立春区间与当前元运 |
| `/api/fengshui/monthly-stars` | `fengshui_monthly_stars` | `query_at` 或 `effective_solar_year/solar_month_number` | 十二节换月中性月星落宫与固定释义 |
| `/api/fengshui/xuankong-house-chart` | `fengshui_xuankong_house_chart` | `house`（磁北宅向）、历史 `period`，可选测量误差与 `interpretation` | 运/山/向盘、下卦/替星与分界候选 |
| `/api/fengshui/assess` | `fengshui_assess` | 住宅、住户、环境、年度或历史宅运输入；`analyze_layout=true` 时评估布局 | `layers.*` 分层盘与 `layout_analysis` |

同一宅向的已知测量误差通过 `house.bearing_uncertainty_degrees` 在八宅与玄空层共同传播（参见[共享宅向误差](interpretation/fengshui/house-bearing-uncertainty.md)）。角度范围 `0..360`，八方与玄空输入须显式声明参考北 `north_reference=magnetic|true`（玄空当前版本要求 `magnetic`）。

## 三端调用示例

将以下虚构输入保存为 `home.json`（完整示例见 [fengshui-home.json](examples/fengshui-home.json)）：

```json
{
  "house": {"object_id": "home", "facing_degrees": 180, "north_reference": "magnetic", "orientation_basis": "measured"},
  "occupants": [
    {"subject_id": "a", "effective_birth_year": 1990, "gender_convention": "male"},
    {"subject_id": "b", "effective_birth_year": 1990, "gender_convention": "female"}
  ],
  "features": [
    {"object_id": "pond", "direction": "S", "classification": "water", "classification_basis": "user_confirmed", "evidence": "已确认南方为水体"}
  ],
  "effective_year": 2026
}
```

```bash
# REST
curl -X POST http://localhost:8010/api/fengshui/assess -H 'Content-Type: application/json' --data-binary @home.json

# CLI（嵌套请求使用 --request-file，显式参数可覆盖文件顶层字段）
uv run --extra dev fatebridge fengshui_assess --request-file home.json --detail compact
uv run --extra dev fatebridge fengshui_minggua --effective-birth-year 1990 --gender-convention female
uv run --extra dev fatebridge fengshui_annual_stars --query-at '2026-02-04T04:03:00+08:00'
```

## 规则版本与来源

规则数据打包在 `src/fatebridge/data/fengshui/`，每项结果在 `rulesets` 与 `source_catalog` 中提供作者、版本与出处（详见[规则来源](interpretation/fengshui/rule-sources.md)）：

| 规则集 | 范围与约定 |
| --- | --- |
| `houtian_directions_v1` | 后天八卦、固定宫数、八方与 24 山角区 |
| `bazhai_sitting_v1` | 坐山起伏位、1864 锚点命卦（默认立春换年，可选 `january_1`）、累计变爻与位置/朝向规则 |
| `jinsuo_basic_fixed_v1` | 一二三四砂、六七八九水与已确认特征逐项判定 |
| `annual_zibai_lichun_v1` | 年度紫白入中、立春区间与当前元运 |
| `monthly_zibai_solar_v1` | 十二节月紫白与固定释义（参见[月紫白参考](interpretation/fengshui/monthly-stars.md)） |
| `xuankong_zhongzhou_v1` | 中州派历史定运、下卦、兼向替星与有限解释（参见[玄空](interpretation/fengshui/xuankong.md)） |

## 布局、室内形态与扩展输入

在 `fengshui_assess` 中启用 `analyze_layout=true` 后可传入 `placements`（门、床、书桌、灶具位置与朝向）、`scene=workstation|shared_rental|home`、`layout_constraints` 与 `layout_alternatives`（参见[场景规划](interpretation/fengshui/scene-planning.md)）。此外支持：

- `form_observations`：现代作者室内控制位置（入口可见、避开入口直线、实体背靠，支持 `methods=[]` 独立评估，详见[布局形态规则](interpretation/fengshui/layout-rules.md)）。
- `environmental_context` / `interior_relations` / `material_facts`：多层/院落对齐、厨卫/床灶/镜面/梁管关系及材质器形资格（详见[室内关系与材质规则](interpretation/fengshui/sourced-interior-rules.md)）。
- `element_adjustments` 与 `annual_remedy_ruleset_id=pang_2026_annual_v1`：绑定已计算对象作用域的五行或年度方案。
- `workstation_layout`：人工标注坐标多边形的实测工位几何计算与有限候选搜索（参见[实测工位](interpretation/fengshui/measured-workstation.md)与[工位作者规则](interpretation/fengshui/workstation-authored.md)）。

## 分层状态与覆盖边界

调用方需区分协议成功、计算状态（`status=complete|partial`）、规则覆盖（`coverage`）与动作可执行性（`layout_analysis.analysis_progress`）：

- 合法缺失输入（如缺住户或仅知朝向缺位置）返回 `partial` 而非错误；未请求方法留在 `coverage.not_requested_layers`。
- `analysis_progress.interpretation_status`（`available` / `conditional` / `scope_only` / `insufficient_evidence`）独立决定当前可解释范围；照片仅保留为待确认候选，动作未 `ready` 不阻塞解释已有盘面事实。
- 完整古典形势、金锁 24 山细断与自动户型识别未实现，列入 `unsupported_queries`。玄空内部数字矛盾返回不可重试错误 `fengshui_calculation_inconsistent`。
