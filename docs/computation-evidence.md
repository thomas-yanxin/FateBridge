# 方法登记、误差预算与执行证据图

这三项合同分别表达方法是什么、误差界知道多少、实际结果依赖哪些输入和规则。登记、执行成功、数值精度、原典符合及现实效度分别验收。当前方法登记不涵盖 `bazi_personality`；领域计数见下文。

## 方法登记

`services/method_registration.py`按实际领域计算登记65个共享方法，覆盖当前92个目录工具；`bazi_personality`明确排除。新增工具没有登记会在目录装配时失败。出生公共计算、各时运层、数算与卦象、各中式盘、西占各推运/事件、印占、人类图、风水以及知识/导出分别登记。人类图可选太阳点质量模型有独立方法、前提及输出范围。

完整发现返回`method_contracts`和`method_registration`，摘要返回`method_ids`。合同包括实际实现路径、维护来源、输出范围、数量类型、单位、前提、选项字段、依赖、误差源及比较条件，并进入`contract_sha256`。`contract_v1`是登记合同的版本，不能冒充上游算法或原典版本。

每次执行还在`run_metadata.calculation_evidence.runtime_method_registry`登记实际返回的`method_id/ruleset_id/resolution_policy`及见证路径。它与公开领域登记分开：实际出现不代表验证通过；没有版本的事实也不自动补为最新版。`method_contract_coverage=declared_subset`保留此边界，不承诺全部内部子函数或所有流派都已独立认证。

适用输入先由已发布输入Schema和领域前提核验。Schema允许某日期或纬度，不等于已有该范围的独立精度证明。条件、已知限制和实际后端仍须读取领域输出；并未实现一个凭缺少资料即可宣称完整可算的自动裁定器。

## 统一误差预算

`core/error_budget.py`区分`bounded`、`declared`、`unquantified`和`not_applicable`。未知不填0；原始钟时的分秒位数不充当精度。调用方声明的出生范围标为条件范围，不认证出生记录或连续区间稳定。

公开出生范围选项的0表示未评估，不能转成已声明的零误差区间。

账本分别维护民用钟、太阳钟、历法、地点、地球自转、星历、求解、显示量化、北向基准和规则裁定。秒、角度、离散规则及未明确量纲不会混加。相同来源不能重复计入；已知同量纲区间采用最坏情形和，不假设独立或做RSS。区间求和按精确有理数计算并向外舍入，避免浮点结果缩窄误差界。

`circular_sector_candidates`能给出已知角误差闭区间在等分圆周上的完整候选，包括跨0°和恰好落界；这只证明该数学映射，不推导出生误差、星历物理误差或其他领域的连续状态。它不产生候选概率。

实际回执的`error_budget.source_bounds_by_unit`只合并来源界。输出量还需有对应的有界传递或完整区间求解；当前未取得时，`output_error_bounds=null`且`output_propagation_status=unquantified`。求根残差、最终浮点括区、出版容差和显示量化不被转写成物理准确率。框架能够传递已知界及未知状态，并未给全部现有输出制造统一置信区间。

`source_coverage_complete=false`表示来源分量仍是合同声明的子集。某量纲没有已登记分量时的`not_applicable`只针对这份来源集合，不能推为该方法没有其他误差来源。

`conditional_output_bounds`交付已核验的局部数学关系：五行精确分量到扶抑量与比例、太乙环路与整数和、奇门值使九宫步进，以及人类图名义太阳投影的有理区间。每项列明输出路径、操作数摘要、精确有理上下界、数学值减已报告值的有符号误差界。离散宫位返回确切类别，不伪造数值置信度。三角函数界沿用已有整数区间实现的解析余项和向外舍入；未采用机器浮点近似值充当严格端点。

这些界以所记操作数和具名规则成立为条件；零算术误差不证明输入无误，也不证明传统有效力量或天体物理精度。来源候选的有限包络另列，`alternatives_exhaustive=false`，不充当全部可能规则或连续不确定性的包络。全局`output_error_bounds`仍为null，未闭合的误差源继续保留。

## 执行证据图

`core/evidence_graph.py`产生`execution_dependency_dag_v2`，绑定本次语义输入摘要、环境摘要、完整业务摘要、每个输出业务根及其子树。路径用JSON Pointer，字面键中的点、斜线和波浪号不会与嵌套路径混同。节点保留显式状态与方法版本，输入区分提供、默认、显式null、缺失和本次生成；嵌套输入的提供路径另列。

边有不同含义：

- `declared_input_dependency/declared_output_dependency`：方法合同声明的保守依赖，允许多算受影响范围，不遗漏可能输入。
- `contains`：只表示包含，不能当作因果证明。
- `rule_input_witness`：从已有领域账本的具名节点和`participants/depends_on/evidence_ids/source_node_ids`解析的规则输入见证。
- `verified_math_operand`：同一完整结果的具体操作数到已重建数学关系；节点另列`verified_given_recorded_operands`与`upstream_value_not_proved`。

规则ID按最近可唯一识别的容器绑定，重复或不明确的身份保留未决，不选第一个。图检查节点唯一、引用闭合、边不重复和无循环。`affected_nodes`返回更正后的保守重算集合，`shared_input_origins`显示结论共享的原始事实，不据多方法一致增加独立置信度。

所有业务根均被子树散列覆盖；这与完整因果读集的证明不同。`resolved_rule_dependencies`和`unresolved_rule_dependencies`分别交付，`semantic_dependency_proof_complete=false`明确保留尚未完成的细粒度语义证明。完整图没有删掉未知边，也没有把一个领域方法节点包装成所有内部因果关系均已证明。

`verified_output_relations`绑定每个具名关系的全部操作数及输出JSON Pointer和摘要，复核时重建关系，不能仅靠篡改后重算摘要蒙混通过。太乙完整起终宫环路还核对每个经过位置及加数，不只核对总和。`source_conflict_certificates`将同次公式结果与原表字面值绑定，保留两边、有限候选和未裁定的来源优先级。它们证明所记录约束不能同时成立，并不裁定原书误刻或优先采用通则。

这批核验是条件数学关系的证明；`producer_instruction_read_set_attested=false`，没有将重建关系冒充生产者机器指令读集或全部上游因果关系的证明。全144太乙核心、1080奇门值使行可用`scripts/validation/audit_verified_output_relations.py`重验。

MCP在入口复用已校验请求，避免框架填默认值后再次建模而丢掉提供字段信息。REST、MCP、CLI对同输入的证据回执一致。

## 大图与同次读取

图和误差账本随原完整run保存。响应预算不足时，`run_metadata.calculation_evidence`保留摘要、散列与`delivery_path`，完整内容列入`result_delivery.deferred_fields`。使用同run的字段分页读取，路径为`run_metadata.calculation_evidence`；不重算原结果。业务首轮预算及完整源事实的要求保持原值，恢复后仍须核对原artifact散列和完整回执。

## 固定总体的专业验收

`validation/acceptance.py`要求固定case ID全集、参考摘要、比较方式、量纲与容差。缺行、重复、额外行、参考不一致和未知均不通过，不由一个成功子集替代分母。数值、来源、解释和现实效度分别列轴。

`scripts/validation/check_framework_gate.py`独立读取原封存JPL参考，用报告中的实际黄经重新比较，不相信报告已写的误差或passed字段；保留原两个后端、24000个位置/后端、1200个设计根/后端，以及2角秒和5秒门槛。

原生 Swiss、Moshier 与显式点质量候选分别保留自己的固定总体和门槛。当前原生位置队列仍有失败，候选的有限队列通过不替换原失败，也不建立全域物理误差界；逐项数字、来源、前提与重验统一见[人类图模型对照](human-design.md#显式视位置模型对照)。

其他领域的审计结果、失败行与未决项见[算法状态](algorithm-status.md)及对应专题。方法登记、协议和回执契约不改变专业验收的原典读数、参考值、门槛或分母。
