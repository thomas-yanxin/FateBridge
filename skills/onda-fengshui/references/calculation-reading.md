# 固定释义与同次结果核验

[玄空有限解释](xuankong-interpretation.md) · [固定零正](fixed-lingzheng.md) · [回读完整结果](../../../docs/agent-guide.md#完整结果交付与同次导出)

`fengshui_natal_calculation_reading_v1@1.2.0` 是工程释义版本，不是新门派或新的吉凶算法。明确请求 `interpretation` 时默认返回顶层 `calculation_reading`，也可显式设置 `include_calculation_reading=false` 关闭。未请求解释时不生成该分支，不自动选流派；历史宅盘、时令、城门、固定零正及现场条件的算法不变。

```json
{
  "current_period_number": 9,
  "period_evidence": "示意：评价运已单独确认，不作为真实用户事实",
  "include_calculation_reading": true
}
```

它解释玄空历史盘、当令存在条件、有序五行、已请求的王氏基本时令、床门有限用途、固定零正和独立城门条件。`uncovered_layers` 明列同次合参中其他方法，`uncovered_topics` 保留完整形势、材料、动作、自由模型正文及现实事件等未覆盖范围，不把这份玄空释义称为全宅或所有方法的验收。

## 每句绑定目标与上下文

`statements` 的每项包含：

- `kind`：历史结构、评价运、具体宫位、用途、固定零正或城门等释义类型。
- `target_path`：原始业务结果中的精确对象路径；E、NE等方位用路径区分，不用正文子串搜索。
- `text`：固定中文模板。具体宫位与用途保留历史宅运和评价运；固定地盘及城门保留自己的参考运。候选、观察事实和条件运算分别说明。
- `basis_paths`：必须同时保留的父候选、评价运、来源、限制及精确目标引用，不能只摘一个 `condition_match=true`。

`target_path` 用于原始结果定位和同run字段回读，不等同计算请求的 `fields` 投影表达式；数组数字索引应按交付资源规则读取。

`basis` 保存这些路径对应的原始完整值，`text` 字段是全部段落的顺序连接。反向五行关系、非当令不等于凶、尚未覆盖、未知和照片候选均有不同表述。五运未知保留两组释义；原始条件运算为假也会说明，不能只用“待确认”替代已有的反面观察。王氏基本死气与互用成员可同时保留，原书差异不隐藏。

评价运未知时，互用数列的空值表示未确定，不能解读为不存在互用星。固定零正与飞星的比较分别标明候选性来自宅盘、五运分段或两者；每个宫位的分段状态保持独立，不被上一项比较的措辞覆盖。

历史宅盘资料缺失时不补星数或宫位，但独立子层已返回的固定零正或城门参考事实仍分别解释，不能用一个缺项遮住其他层。

1.1.0对每个宅盘候选补充全部已返回的三组同宫合十、九宫父母组、固定地盘全盘与局部反伏数式、历史运盘重叠及卷二有限局名对应。每一对、每一宫和每一侧各自绑定目标，负面全盘状态不掩盖局部匹配。这里的合十是同一宫两盘的和，不替代异宫对角合十或夫妇用法；父母组匹配不推定普通三般、七星打劫或现实取用。数式的详细参照见[数字结构](classical-patterns.md)。

1.2.0在规则1.4.0的每个候选上再加一段山向对宫汇总与八段有方向的逐项解释，共九段。山星所在宫与向星所在对宫均绑定具体目标，中宫只作数字相加，不设空间对宫，也不混进八宫合取。同宫、异宫、固定地盘反吟数式和特定原书局名继续分开；替卦的算数关系不继承原书下卦例的吉凶或应期。

`status=rendered` 只表示本释义版本完成了渲染；不表示当前输入、全部形势或预测效力验收完成。未知规则版本或不匹配的来源登记返回 `unsupported_context`，原始计算结果仍保留，不能据此授予解释一致性通过。

首轮选择摘要字段时，若已请求解释且未关闭固定释义，在 `fields` 中追加顶层 `calculation_reading`。严格投影不会自动补选新分支；只读到摘要时可以解释该内容，但不能声明完整原始业务结果已核验。

## 核验原始运行

核验函数为 `fatebridge.validation.fengshui_reading.verify_fengshui_reading`。必须从可信执行端独立保管同次运行的完整 `run_metadata`，通过 `trusted_run_metadata` 传入；不要在被核验的文件中重新计算散列后把它当可信回执。

```python
from fatebridge.validation.fengshui_reading import verify_fengshui_reading

report = verify_fengshui_reading(
    original_full_response,
    trusted_run_metadata=separately_retained_run_metadata,
)
```

它核对整份原始业务结果散列、全部回执字段、精确文字、目标路径、上下文原值、候选与段落覆盖。漏掉不利数字条件、删除另一半候选、换用新run、修改引文或追加确定预测均不能通过。压缩后的行内回执须先从同次运行的可信 manifest 恢复完整回执；不把缩略回执当完整环境，也不重算来替代原run。

校验器按原响应的已知释义版本核验，保留1.0.0与1.1.0原有文本合同。1.0.0不追授一般数式覆盖；1.1.0可核验原16段数式，但不追授对宫覆盖；1.2.0核验通过且确有宅盘候选时，才返回 `opposite_palace_coverage_verified=true`，并以 `opposite_palace_chart_count`记录候选数。一般数式仍以 `numeric_structure_coverage_verified`／`numeric_structure_chart_count`分开记录；缺历史盘或未知版本均不能得到相应覆盖信用。版本不是排盘请求参数；新服务输出1.2.0。修改版本、删新段落并重算待验文件的散列，不能替代独立保管的原始回执。核验旧run读取完整原响应，不用新算法重算旧请求冒充原运行。

需要核验时，首次保留完整业务结果：`fields=null`，`include_snapshot_text=true`。默认预算分页可用，但需读取同一 `result_delivery` 的完整结果。首轮已投影或删除的原始字段不能凭释义补回；缺完整业务数据时核验拒绝，而不是重新计算后冒充原run。

回执相符与数式成立须分别检查。1.1.0／1.2.0的数式覆盖现在还要求派生结构与原三盘一致，涵盖逐宫求和、全局合取、父母组、地盘参照、历史运盘重叠和有限局名；1.2.0另查八个有向空间对宫及独立中宫。矛盾时增加 `numeric_structure_inconsistent` 并拒绝，`derived_numeric_consistency_verified=false`，不能因释义忠于错误派生值而取得覆盖信用。正常且有候选时该标记为true；1.0.0不追授数式检查，也不要求旧1.1.0包含后来新增的对宫分支。原始响应、实际原文和回执不改写，这仍不是任意自由文本、所选规则原典正确性或预测效力的认证。

仓库审计命令：

```bash
uv run --locked --extra dev python -m scripts.fengshui.audit_fengshui_reading \
  --payload original-full-response.json \
  --trusted-receipt separately-retained-run-metadata.json
```

`--payload` 也接受同次结果存储文件的 `payload` 对象包装。退出0只表示 `verified_served_fixed_reading`；不重新计算或独立证明底层算式正确，也不认证任意自由改写、输入事实真实性、原典全本或现实预测，报告中的相关标记始终为false。回执来源的真实性仍由调用方负责；散列比较不是数字签名。

咨询可以引用这些计算依据，再分开给传统含义和现实建议。额外自由生成的段落不能借用固定释义的核验状态，新增现实建议也不能冒称来自某个星数或作者原句。

## 作者基本时令与图位的内部一致性

作者子版本`wang_zhongzhou_timeliness_v1@1.1.0`增加先后天图位来源，固定释义1.2.0逐候选与山向角色解释。校验器把基本时令、互用成员和有向图位绑定回原盘星数及同次评价运；错误标签不能因与正文、回执互相吻合而通过。旧作者1.0.0仍检查原有基本时令和成员数字，图位覆盖计数为零。

`author_geometry_record_count`表示核对的新版记录数，`author_geometry_derived_record_count`只计两条图位推导；五运和未知运分别进入`author_geometry_five_table_only_count`及`author_geometry_unknown_count`。只有确有推导且新版固定文本完整时，`author_geometry_coverage_verified`才为true。五运的原表数字不算图位推导通过，互用符合也不认证现场可用。详见[来源及保留的原始错误运行](../../../docs/fengshui.md)。

## 主客出入的内部一致性

显式选择 `shen_2011_host_guest_v1@1.0.0` 后，固定释义1.2.0增加每候选八段盘层关系和两段原文对照，见[主客来源及差异](../../../docs/fengshui.md)。独立校验先核原三盘、方向、主客角色、实际星数、五行定义及固定比较基准，再核回执与模板；同五行换星数和逐例换比较对象也不能通过。错误记录 `host_guest_inconsistent`，不会因为正文忠于错误数据而获得覆盖。

`host_guest_relation_count`为实际核对关系数，`host_guest_coverage_verified`还要求1.2.0的关系文本完整。`host_guest_literal_source_matches`、`host_guest_literal_source_differences`、`host_guest_ambiguous_source_roles`单列原文槽状态；出现真实来源差异并不等同内部计算错误，前者完整保留后仍可交付，不能因此把全书符合标为true。旧响应不含该层时计数为零，旧1.0／1.1不追授新文本覆盖。

## 新运行的原书数表分支

含 `source_comparison` 的运行，固定释义逐候选引用同次比较记录及实际宅盘。新比较版本2.0.0中，下卦核对正文四字段和图数；替卦仅核对起星图27数，说明卷五编者范围、正文与兼向条件未验证。七运申寅保留“原图五、计算二”；五运子午替卦保留南宫山星“原图九、计算六”。相合只限实际列出的数字成分，未算出宅盘没有比较信用。旧1.0.0比较记录与未含此分支的旧固定模板仍按原语境核验，不能追授起星图覆盖。任意自由模型正文仍未认证。完整来源见[运行来源比较](../../../docs/fengshui.md)。
