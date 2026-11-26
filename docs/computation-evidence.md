# 方法登记、误差预算与执行证据图

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

这三项合同分别表达方法是什么、误差界知道多少、实际结果依赖哪些输入和规则。登记、执行成功、数值精度、原典符合及现实效度分别验收；领域计数见下文。

## 方法登记

当前 93 条公开目录记录关联 66 个唯一 `method_id`，由 `services/method_registration.py` 登记。新增工具没有登记会在目录装配时失败。出生计算、各时运层、数算与卦象、各中式盘、西占各推运与事件、印占、人类图、风水以及知识与导出分别登记。人类图可选太阳点质量模型有独立方法、前提及输出范围。

`bazi_source_compare` 直接使用给定四柱，登记字面排柱校核与来源对照。`ziwei_rules` 按所选规则查询资料，登记紫微规则目录。两者的声明误差源均为 `rule_adjudication`。`ziwei_birth`、`ziwei_horoscope` 和 `ziwei_rules` 均将实际生效的 `sihua_source` 列为方法选择器。

`bazi_personality`复用出生前置合同，并单列`bazi_personality_symbolic`的计数和文化词义。非日干每次1、每个藏干每次0.5；按出现量取前三名并保留截止位同分，首位同分也全部列出。这是工程计数，不能测量性格强弱。日干五行阴阳、工程旺衰与词典叙述分别核对；五行、十神的具体文字来自FateBridge编辑词典，尚未逐条完成原典符合或现实人格效度验收。该方法登记不补造古籍来源、不等于人格量表，也不认证附带的时运层。

出生合同将 `personality_analysis` 整体登记为保守依赖根，覆盖范围以方法声明为准。性格词典及计数不读取性别、大运或流年参数，这些参数记录在外层时运上下文中。

完整发现返回`method_contracts`和`method_registration`，摘要返回`method_ids`。合同包括实际实现路径、维护来源、输出范围、数量类型、单位、前提、选项字段、依赖、误差源及比较条件。`contract_v1`是登记合同的版本，不能冒充上游算法或原典版本。

`detail=audit` 的 `run_metadata.calculation_evidence` 包含 `registered_methods` 和 `error_budget`。`run_metadata.provenance` 汇总本次业务实际返回的 `method_id`、`ruleset_id`、`resolution_policy` 等版本事实。具体规则、操作数和来源由各工具的业务字段提供，可按其 `evidence_views` 选择字段。

`otherbu` 在发现合同中列出骰面符号和独立天象两种方法。`requires_non_null_output="chart"` 要求投影前的完整业务结果提供非空 `chart`，该次执行才登记天象方法及其误差源。`diceChart` 的方法归属是骰面符号。业务字段投影沿用同一次执行的完整 `run_metadata`。 [固定三端对照](precision-acceptance.md#conditional-method-address-round209)

适用输入先由已发布输入Schema和领域前提核验。Schema允许某日期或纬度，不等于已有该范围的独立精度证明。条件、已知限制和实际后端仍须读取领域输出；并未实现一个凭缺少资料即可宣称完整可算的自动裁定器。

## 统一误差预算

`core/error_budget.py`区分`bounded`、`declared`、`unquantified`和`not_applicable`。未知不填0；原始钟时的分秒位数不充当精度。调用方声明的出生范围标为条件范围，不认证出生记录或连续区间稳定。

公开出生范围选项的0表示未评估，不能转成已声明的零误差区间。

正值民用出生范围可以声明 UTC 经过时间界。使用民用记录并选择真太阳时显示时，仍按民用记录处理。地方平太阳时和地方视太阳时的声明范围附在各自的记录钟面上，民用 UTC 来源界保留为未量化。 [出生记录钟基与固定三端对照](precision-acceptance.md#recorded-clock-error-budget-round140)

账本分别维护民用钟、太阳钟、历法、地点、地球自转、星历、求解、显示量化、北向基准和规则裁定。秒、角度、离散规则及未明确量纲不会混加。相同来源不能重复计入；已知同量纲区间采用最坏情形和，不假设独立或做RSS。区间求和按精确有理数计算并向外舍入，避免浮点结果缩窄误差界。

`circular_sector_candidates`能给出已知角误差闭区间在等分圆周上的完整候选，包括跨0°和恰好落界；这只证明该数学映射，不推导出生误差、星历物理误差或其他领域的连续状态。它不产生候选概率。

实际回执的`error_budget.source_bounds_by_unit`只合并来源界。输出量还需有对应的有界传递或完整区间求解；当前未取得时，`output_error_bounds=null`且`output_propagation_status=unquantified`。求根残差、最终浮点括区、出版容差和显示量化不被转写成物理准确率。框架能够传递已知界及未知状态，并未给全部现有输出制造统一置信区间。

`source_coverage_complete=false`表示来源分量仍是合同声明的子集。某量纲没有已登记分量时的`not_applicable`只针对这份来源集合，不能推为该方法没有其他误差来源。

离线审计的 `conditional_output_bounds` 记录已核验的局部数学关系，覆盖五行精确分量到扶抑量与比例、太乙环路与整数和、奇门值使九宫步进，以及人类图名义太阳投影的有理区间。每项列明输出路径、操作数摘要、精确有理上下界和数学值减去报告值的有符号误差界。离散宫位返回确切类别。三角函数界沿用整数区间实现的解析余项和向外舍入。

这些界以所记操作数和具名规则成立为条件；零算术误差不证明输入无误，也不证明传统有效力量或天体物理精度。来源候选的有限包络另列，`alternatives_exhaustive=false`，不充当全部可能规则或连续不确定性的包络。全局`output_error_bounds`仍为null，未闭合的误差源继续保留。

## 离线执行证据图

离线代码通过 `validation/evidence_graph.py` 生成 `execution_dependency_dag_v2`。审计传入原始请求及完整业务事实，图绑定输入、环境、业务和输出子树的摘要。路径使用 JSON Pointer，节点保留实际版本及显式、默认、显式空值、缺失和本次生成等输入状态。

边有不同含义：

- `declared_input_dependency/declared_output_dependency`：方法合同声明的保守依赖，允许多算受影响范围，不遗漏可能输入。
- `contains`：只表示包含，不能当作因果证明。
- `rule_input_witness`：从已有领域账本的具名节点和`participants/depends_on/evidence_ids/source_node_ids`解析的规则输入见证。
- `verified_math_operand`：同一完整结果的具体操作数到已重建数学关系；节点另列`verified_given_recorded_operands`与`upstream_value_not_proved`。

规则ID按最近可唯一识别的容器绑定，重复或不明确的身份保留未决，不选第一个。图检查节点唯一、引用闭合、边不重复和无循环。`affected_nodes`返回更正后的保守重算集合，`shared_input_origins`显示结论共享的原始事实，不据多方法一致增加独立置信度。

执行图覆盖全部业务根；完整因果读集仍需独立证明。`resolved_rule_dependencies`和`unresolved_rule_dependencies`分别交付，`semantic_dependency_proof_complete=false`明确保留尚未完成的细粒度语义证明。完整图没有删掉未知边，也没有把一个领域方法节点包装成所有内部因果关系均已证明。

`verified_output_relations`绑定每个具名关系的全部操作数及输出JSON Pointer和摘要，复核时重建关系，不能仅靠篡改后重算摘要蒙混通过。太乙完整起终宫环路还核对每个经过位置及加数，不只核对总和。`source_conflict_certificates`将同次公式结果与原表字面值绑定，保留两边、有限候选和未裁定的来源优先级。它们证明所记录约束不能同时成立，并不裁定原书误刻或优先采用通则。

这批核验是条件数学关系的证明；`producer_instruction_read_set_attested=false`，没有将重建关系冒充生产者机器指令读集或全部上游因果关系的证明。全144太乙核心、1080奇门值使行可用`scripts/validation/audit_verified_output_relations.py`重验。

MCP 在入口复用已校验请求，保留显式提供的字段。REST、MCP、CLI 对相同输入返回一致的方法登记和声明误差预算。

## 同次读取

响应超出预算时，交付层将已选业务结果和回执写入同一份本地 JSON。若误差预算延后交付，回执提供 `delivery_path`，`result_delivery.deferred_fields` 列出对应路径。经验证的分页按原 `run_id` 读取，私有文件的整份载荷摘要用于核对保存内容，读取过程复用原结果。

## 固定总体的专业验收

`validation/acceptance.py`要求固定case ID全集、参考摘要、比较方式、量纲与容差。缺行、重复、额外行、参考不一致和未知均不通过，不由一个成功子集替代分母。数值、来源、解释和现实效度分别列轴。

`scripts/validation/check_framework_gate.py`独立读取原封存JPL参考，用报告中的实际黄经重新比较，不相信报告已写的误差或passed字段；保留原两个后端、24000个位置/后端、1200个设计根/后端，以及2角秒和5秒门槛。

原生 Swiss、Moshier 与显式点质量候选分别保留自己的固定总体和门槛。当前原生位置队列仍有失败，候选的有限队列通过不替换原失败，也不建立全域物理误差界；逐项数字、来源、前提与重验统一见[人类图模型对照](human-design.md#显式视位置模型对照)。

其他领域的审计结果、失败行与未决项见[算法状态](algorithm-status.md)及对应专题。方法登记、协议和回执契约不改变专业验收的原典读数、参考值、门槛或分母。
