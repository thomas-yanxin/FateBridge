# 风水咨询闭环

[场景技能](../SKILL.md) · [规则来源](rule-sources.md) · [结果交付](delivery.md) · [工程接入](../../../docs/fengshui.md)

本参考组织工具与咨询边界；参数以连接中的定义为准，规则以返回的版本、作用域和来源为准。主要方法为九宫飞星、金锁玉关和八宅，执行用户提供的专家访谈口径 `user_expert_policy_v1`（2026-10-15）。无需用户先提供全套住宅与出生资料。

输出先回答用户的空间问题；逐对象完整审查及多方案比较按[结果交付与方案对照](delivery.md)呈现，让每项结论能回到现场事实和实际返回的规则。单项问题无需加长为整宅报告。

有一项有效事实就先回答这一项：说明判断、实际规则为什么关注这个关系，以及它与用户问题的联系，再给可考虑的方向。传统理由取自实际规则与来源，现实使用建议单独说明。照片用“从照片看……，若现场如此……”表达条件，同时交付已有理由。落实具体动作时再核执行许可、容纳、通行及操作空间；必要的定宫、宅运及计算校验只约束依赖这些输入的结论。

读取 `analysis_progress.interpretation_status`：`available` 解释已有确认判断或参考，`conditional` 交付条件判断，`scope_only` 说明未覆盖，`insufficient_evidence` 则先找出本次最关键的一个可观察事实。`follow_up.conclusion_candidates` 按用户所问筛选，必要时选一至两项，用日常问题与简便观察方法取得；`execution_only` 留到落实对应动作时。用户表示不知道、无法提供或暂不测量后，保留当前可答部分与条件，结束这一轮补问。未实现、无规则或作者不覆盖的年份直接说明能力范围。

本页按咨询步骤查阅：[核对必要事实](#按请求核对资料)、[选择方法和读取结果](#选择和读取结果)、[交付与复核](#交付与复核)。字段细节按主题转到[候选布局](scene-planning.md)、[室内关系与材质](sourced-interior-rules.md)、[工位作者规则](workstation-authored.md)、[桌面作者法](surface-rules.md)；不要求一次读取或提交所有分支。

## 按请求核对资料

| 请求层 | 必要事实及如何处理缺失 |
| --- | --- |
| 户型方位门槛 | 空间范围、图纸旋转／偏移、参考北、已确认立极与分宫；宫位未知不由命盘或屏幕上下补齐。通用年盘可排，具体房间落宫仍待确认 |
| 对象方向／个人匹配 | 对象用途、已确认位置或朝向、适用使用人；住户按命卦的三选一生年路径。缺宅向仍可保留个人关系；对象未知方位省略，禁止占位臆造 |
| 室内形态 | 从本次所问的一项具体观察开始，可独立 `methods=[]`。例如坐好是否能看见入口、背后是否有实体支撑；照片保留条件依据，其余未知项省略 |
| 桌面作者法 | 用户明确另选现代 BTB 后，核对矩形、坐者近沿、事业／丰盛目标、物件代表属性及依据；桌面请求或目标本身不构成选用 BTB，不能代替无方位的飞星／金锁 |
| 金锁基础层 | 环境特征的方位、砂／水／混合／未知分类及依据；照片或物品名称不证明分类 |
| 年盘 | 有效年或含时区查询时刻；采用立春边界，不把公历年自动当有效年。年度物件作者规则须显式选择且限支持年份 |
| 玄空 | 磁北宅向及测量不确定度、历史定运事件和依据、明确版本；资料不足就保留候选／缺失，不用当前年份补齐。请求有限解释时另核当前运及证据、全宅分宫外部山水观察，按[有限解释参考](xuankong-interpretation.md)读取；不以金锁砂水、室内靠背或照片推断外局已确认 |
| 家庭人物 | 已确认同住范围、辈分、父母／子女关系、本人与丈夫排行（妻随夫须显式）、实际使用空间；生肖独立确认。仅解释象意用 `household_scope=symbolic_reference`，不追罗盘；关联实际环境用默认 `environmental_binding` |
| 多层／院落 | 各层范围及用途、显式共用方向、逐层图纸对齐及中心确认、实际住／用人；院落及绿化归一层，并复核共享外局、门路、跨层互动。异层是否适宜和局部影响是否限层须有独立依据 |
| 双对象室内关系 | 按[本轮规则清单](sourced-interior-rules.md)确认源／目标角色、精确关系、present true／false／null及独立依据；床灶上下须确认垂直投影，床位柱角限实体柱角，床头／灶背共墙须确认墙另一侧实际便器。旧粗粒度观察不自动转成新关系 |
| 材质／器形／颜色 | `material_facts` 按各属性原粒度记录；`plant_alive` 不由绿色／照片推确认。明确询问代表物资格才给 `element_use`，不将所需元素、个人喜用、摆位可行混入资格问题 |

本表供助手按问题选用，不是请用户填完的问卷。需要精确方位时说明该数值会影响哪项判断，以及最简取得方法；方位与图纸中心尚无法核对，就先交付独立形态或方法解释。落实动作时另记能否搬转、新增、预算、共用范围与不可用区域，物理观察仍按实际证据记录。

节气求解回退且查询/出生时刻接近立春时，年星及命卦会保留有效年候选并要求确认有效年；不能把近似交节当精确归年。明确有效生年/有效分析年仍可使用；不以当前元运补历史宅运。

`entrance_position`、`passage_position`、`window_position` 使用 `front/front_left/front_right/left/right/back/back_left/back_right` 这八种相对位置，未知省略；中文“左侧”不能自行拼成 `left_side_of_bed` 等值。定义仍以当前 schema 为准，校验失败按 issues 的路径和允许值修正一次，不重复失败输入。

## 工位作者扩展

书桌实际工作／学习活动、明确入口与坐者的隔挡关系，按[工位作者规则](workstation-authored.md)提交 `environmental_context.workstation_review` 并读取 `layout_analysis.workstation_analysis`。材料附加条件在 `material_facts.application` 与 `material_analysis`，不能由代表物资格推摆放位置。每条规则显式选作者版本；普通解释不等待执行状态。WOFS 非 BTB 桌面规则仍仅作参考。

## 桌面坐标与证据

桌面均分三行三列：`near` 靠身体、`far` 远离身体；`left/right` 以坐着使用者为基准。近左/近中/近右对应 `near_left/near_center/near_right`，中排对应 `middle_left/middle_center/middle_right`，远排对应 `far_left/far_center/far_right`。不要把房间门口或罗盘方向作为桌面分区锚点。

`surface_layouts` 每项显式 `ruleset_id=desktop_bagua_btb_v1`、`shape=rectangular`、`anchor=seated_near_edge`、`goal=career|abundance`，记录边界的 `observation_basis` 和 `evidence`。每件物品要有 `object_id,label,representation,observation_basis,evidence`；representation 可为 `living_plant/fresh_flowers/water_image/dark_accessory/other/unknown`。不按物品名推元素。

物件属性确认与位置确认是两件事。`zone` 与 `zone_observation_basis` 成对，左右已知但近远未知时不填九格位置；照片所见用 `image_observed`，用户确认用 `user_confirmed`，实际测量用 `measured`。活植物确认不自动确认其位置。

`surface_constraints` 关联同一桌面 ID。`can_move_items/can_add_items` 是许可；`locked_item_ids` 是固定物件；`unavailable_zones` 是不可用区；`feasible_zones` 只列用户明确确认能容纳对象且不遮视野、不影响操作的区域。不从照片空白或允许移动扩展可行区域，未确认时省略。

## 选择和读取结果

工位用 `scene=workstation`，合租局部用 `scene=shared_rental`，家居用 `scene=home`。局部先考虑九宫飞星、次金锁，八宅按明确的人宅问题独立选择；实际能算哪些层仍取决于确认事实。未传 methods 时按现有事实选法，显式列表优先；优先顺序不补缺失输入、不产生合成分。只做形态可用空列表；桌面作者法须用户明确另选。`form_observations` 可以独立存在，不构造无方位的 `placements`。位置和朝向各自观察，给布局计算时 `analyze_layout=true`。元素方案 `element_adjustments` 必须绑定已算对象、方法、作用域和 `drain/support` 目标，不能按个人“缺五行”、八字喜用或相关人命盘开处方。

### 纯方法参考

纯方法、职业／家具或砂水参考可用 `scene=home` 路由、`analyze_layout=false`，按实际计算范围显式选 `methods` 并投影 `method_details`，只查公共静态表可用 `methods=[]`。`bazhai_you_nian_references` 等映射不依赖八宅计算；查表不启动人宅匹配或追生辰。无实际环境事实则省略 `environmental_context`，场景标签不代表房屋、观察或摆位结论。年度对照只另选 `annual_stars` 并给真实有效年／查询时刻；家庭 `symbolic_reference` 仅用于实际已提供家庭资料的说明。

### 已选方法与优先审查

`method_policy.priority_review_status` 与每法 `not_selected_reason` 用于分清本次已审范围、自动缺输入与用户排除。单项问题按该项判断交付，其他层在方法范围中简述；用户要求整体审查或本次结论依赖其他层时，再展开优先方法的必要事实。默认优先序不扩大每轮用户的问题，也不要求用户先完成整套审查。

优先范围状态只针对局部前两法的可用性：非局部或显式空列表可为 `not_requested`，缺计算证据为 `not_assessed`，仍有相关优先方法缺层为 `partial`；`complete` 也不表示实际落宫、全部分支或动作已完整核验。每法 `available_engine_layers` 只列真实已算 complete 的层；`input_ready_engine_layers` 仅表示必要字段存在，不代表已经解算、排除交节候选或确认物理绑定。`priority_missing_inputs` 是可选优先复核提示，不自动升级成用户必须补交的资料。

有候选时，顶层优先状态和 `available_engine_layers` 仍只指现状；另读 `priority_review_by_scope.candidates`、`available_candidate_engine_layers` 及各层 `candidate_calculations`。候选 complete 不升级现状，现状 complete 也不证明候选算完；候选没有真实计算证据时保留 `not_assessed`。

### 环境与家庭人物

`environmental_context` 承载户型方位、家庭、多层及形态事实时，逐项沿用原始证据；按连接中完整 schema 构造，不把此参考中的自然语言概念猜成字段。厨房、卫生间、庭院绿化及普通器物使用其 `objects`，不伪造成门床桌灶占位。方向明确尚未确认时，不同时提交已定宫的 `placements.location_direction`、金锁 `features` 或玄空 `external_forms`；原始宅盘／年盘、命卦和独立形态仍可计算。结果位于 `layout_analysis.environmental_context`，其咨询政策／人物关注与 `layers.bazhai.occupants` 的个人命卦关系分开。家庭主宫、独立确认生肖宫和次级对宫分别解释，不将对宫当本宫同等结论；多层结果也不得自动归成全宅统一吉凶。

家庭宫位先按完整同住辈分决定乾坤归属。`parent` 可保留为事实，但 `withheld_roles.reason=senior_co_resident_generation_takes_parent_palace` 表示其父母宫由同住更高辈占用，不能补宫、标缺失或宣称计算漏算。只有实际 `associations` 同时列父母和排行身份时才交付双宫；同住名单或辈分改变后重算受影响对应。

### 楼层与使用范围

每个 `floors` 空间独立保存 `floorplan_alignment_confirmed`、`center_confirmed`；只有显式 `uses_shared_orientation=true` 才共用全宅已确认方向。全宅方向／中心不能补这些逐层门槛，院落作为独立空间也要核对。缺门槛的楼层关联对象不提交实际落宫事实；各层位置是在各自确认中心下关联本次已声明宅盘／年盘，不自动生成楼层宅运或几何分宫。候选环境也须独立重核这三个逐层状态。

`floors[].subject_ids` 只确认谁使用，不确认未列者不使用；默认空列表仍是未知。需要作“局部影响不归给异层人”或“在共享范围外”的负向排除时，有关作用空间须 `usage_confirmed=true` 与 `usage_evidence` 成对，覆盖相同作用层的室内／院落；缺失保持使用范围待确认。已知正向使用或未进行排除，不把完整名单作为额外必填项。

完整楼层使用名单必须包含该层对象 `placement.subject_id/subject_ids` 明确关联的使用者；省略 selector 的旧兼容语义不当作真实使用声明，也不据此扩充名单。候选仍使用原已确认使用人，不能换人让排除成立。

`household_scope=symbolic_reference` 仅在实际提供家庭资料时输出家庭卦／对宫符号，即使全宅已有方向也不绑定实际方区；没有楼层分析时不为这类家庭象意追罗盘。默认 `environmental_binding` 才核对环境方位。`household_correspondences` 及 `associations` 的 `scope`、`applicable_methods`、`selected_applicable_methods` 明示这些是飞星／金锁环境象征索引，不是八宅命卦；所选仅八宅时不能将它们解释成八宅人宅判定。

### 按需读取结果分支

首轮投影使用工具已公布字段，并为所有风水解读追加 `rulesets` 与 `rule_trace`，以取得本次作者版本和可引用来源；单独命卦也适用。有 `scene` 或环境上下文时首轮追加 `method_policy`，有 `environmental_context` 才追加 `layout_analysis.environmental_context`；旧请求中这些路径可以不存在，不在严格投影里无条件追加。按请求加读这些分支，而不是一次铺满全量：

- 总体状态／覆盖：`status`、`coverage`（含 `analysis_progress`）、`layout_analysis.calculation_scope`、`layout_analysis.missing_inputs`、`layout_analysis.unsupported_queries`、`layout_analysis.limitations`。
- 具体候选：`layout_analysis.alternatives_analysis`；当前审查与候选待确认分开，不自动评分或选赢家。
- 方向行动：`layout_analysis.placement_findings`、`layout_analysis.adjustment_options`、`layout_analysis.environment_adjustments`；个人关系需要时加 `layers.bazhai.occupants`。
- 形态／元素／年度：`layout_analysis.form_analysis`、`layout_analysis.element_remedies`、`layout_analysis.annual_remedies`、`layout_analysis.supplement_statuses`。
- 双对象室内规则：实际提供 `interior_relations` 时读 `layout_analysis.interior_analysis`，核对 predicate、exceptions、method_disagreements、每端动作的权限及缺失条件。
- 属性与代表物资格：实际提供 `material_facts` 时读 `layout_analysis.material_analysis`，分别解释 material／shape／colour reference、资格状态及未知项，不从资格输出摆位／ready。
- 桌面物件：`layout_analysis.surface_analysis`，逐对象看覆盖与行动状态。
- 来源／分歧：`rulesets`、`rule_trace`、`conflicts`、`layout_analysis.method_disagreements`；不能把不同流派关系平均为总分。
- 选法：有场景／环境上下文才读 `method_policy`，核对推荐顺序、实际所选层、`priority_review_status` 与 `not_selected_reason`。方法五行、职业／器物象意或砂水细节请求再读 `method_details`；它是 `reference_only`，不是新的吉凶判定。
- 环境上下文：`layout_analysis.environmental_context` 下的 `orientation_review`、`household_correspondences`、`floor_review`、`environment_findings`、`separation_policy`、`missing_inputs`；保留方向门槛、家庭／生肖及对宫主次、局部／共享层级、专家版本与未覆盖形态。

返回含 `result_delivery.deferred_fields` 时，先检查本次判断、理由及来源是否已在首屏。缺少所需分支就从同一 run 的结果文件或分页读取，按 `file_payload_path` 取业务结果；这属于读取已有结果，无需重算或追加用户资料。区分交付裁剪与真实缺项，再按已有事实回答；`partial` 只描述实际未完成的范围。

## 交付与复核

完整交付的对象清单来自用户本次请求，不能只挑有利或有动作的结果。相关分支已返回时也要保留符合判据、关系不成立和明确未覆盖的项目；具体表格与比较顺序见[交付参考](delivery.md)。

建议按对象说明当前依据、传统理由和可考虑的调整，条件在相关处简洁交代。方法／作者版本与来源集中说明即可。方向候选可用于解释和条件式建议；列为可直接执行的动作前再筛搬转限制、共用方向与实际空间。没有共同方向或没有可行方案时解释权衡，不以摆件替代方向结论。

桌面返回 `ready` 才有已确认物件／边界、许可与可行区；`conditional_option` 写明需确认的条件，`candidate_only` 待核对照片事实，`blocked` 保留约束，`no_independent_placement_rule` 说明无独立摆放规则。无规则也属于完整覆盖的一种结果，但不能称为“算出吉位”。

### 审查完成与动作条件

`analysis_progress` 的 `calculation_status`、`rule_coverage_status` 和 `action_readiness` 各自读取：已确认不属于作者代表物的物件可为 `reviewed_unsupported`，属性 unknown 或照片候选则为 `needs_confirmation`。`assessment_complete` 只表示已提交事实及所选范围的审查可以结束，不证明现场调整已经实施。原 `status=partial` 在无独立规则物件上仍保留兼容语义，不据此要求用户继续补资料。

每个动作的 `pending_confirmations` 只列现有合同尚未确认的门槛，`required_for=optional_action` 不阻止本次事实审查结束；blocked 动作没有执行追问。全局事实确认与动作确认分别处理，例如物件属性未知仍有审查问题，但不追问已禁止移动的目标区。`path` 是确认事项的输入或结果锚点，不能把结果路径当新接口参数传入。对象动作约束用 `layout_constraints`，可关联 `placements`、`form_observations` 或 `environmental_context.objects` 中登记的真实对象；登记对象和许可不新增其方向或形态规则支持。具体方案用 `layout_alternatives`，方向列表仍不是可执行布局。候选的许可、`physically_feasible` 和新位置独立观察各自核对，禁止借用旧形态；ready只说明所选门槛满足，逐规则匹配与现实效果另外说明。作者的现场维护条件继续复核。

`physically_feasible` 只来自逐方案确认的容纳、通行和操作空间，不由动作许可或照片空白推定。候选用途及已确认使用人集合不能偷换；可比较的方向也不自动表示现场可放家具。

### 候选独立重核

候选的环境上下文使用 `layout_alternatives[].environmental_context`，该字段是新方案的独立事实，顶层现状的家庭／楼层／观察不自动继承。现状对象涉及楼层或环境观察时，新方案须独立重核原有维度；缺上下文、空上下文或只重核一部分都不得让该维度跳过门槛而 ready。候选结果读取 `layout_analysis.alternatives_analysis.findings[].environmental_context` 及其缺失项，确认 `old_environmental_context_reused=false`；旧层适宜性与影响范围不能搬到新位置当作确认依据。

若候选目标也是现状金锁 `features` 对象，新方案须提供该对象独立确认的新 `features`：只关联同一 `candidate.object_id`，`direction` 与新 `placement.location_direction` 一致，并保留分类依据和证据。缺新特征仍待确认，不能因许可或空间已确认而 ready。

搬转对象出现在旧 `interior_relations` 任一端时，候选须确认相同 kind／源／目标的新关系；只因另一端固定、替换关系类型或省略旧项均不完成重核。关联 `material_facts` 也维持每个已知属性及代表物问题的原粒度。确认 false、null、照片候选分别处理；关系动作始终只是条件方案或 blocked，不由两端关系审查完成跳过独立物理可行性。

固定另一端已知楼层在候选省略时仍用于跨层校验；目标改楼层／作用域须声明 `location` 并核对搬位许可。已确认的材质、器形、颜色及植物存活布尔不因搬转改变；照片或 unknown 可确认，事实更正先替换现状。每个动作读 `action_basis`，只有 IR2／5／12 原作者明确搬移，其余已登记动作是改变关系的条件工程候选。

镜面、尖角源等候选可仅给新 `environmental_context`，其中须有至少一条涉及候选对象的新关系，不虚构床／桌／灶位置。候选 `rule_comparisons` 的室内关系与材料条目分别限定为关系判据和代表物资格，不当作综合吉凶或可立即执行结论。

其他固定金锁特征不能随目标候选改楼层／坐标；候选上下文省略它们时，`environment_adjustments` 仍保留原楼层元数据。逐规则比较同时看八宅、形态、金锁和已算年星／历史宅盘参考；后两者的 `comparison_scope` 限星数／角色／落宫参考，不扩成完整组合判断。`layer_statuses` 供区分现状与各候选真实计算完成状态，未算的层不能因输入字段齐备就称可用。

### 方法参考与来源归属

方法细节先按 `mapping_boundaries` 选表：固定宫看 `palaces`，实际临宫年／运／山／向星看 `flying_star_references`，八宅游年看 `bazhai_you_nian_references`。`cross_text_trigram_symbols` 的人物／器物是本卦词类；`object_observation_references` 是待核事实提示，不能从词类绑定实际人或家具。逐星主题与有限职业例保留作者页码、组合及用途；其他职业不补造。砂水看 `form_condition_references`，各法门床灶／星角色细节看 `application_references`，材料／器形参考看 `material_shape_reference`，均不自动产生摆位处方。

来源分层：九条专家口径标注为用户提供的 `user_expert_policy_v1`（2026-10-15，未提供专家署名／原始访谈稿，不冒充经典共识）；八宅／金锁／年度与历史玄空引用[基础规则与来源](rule-sources.md)和[历史宅盘资料与来源](xuankong.md)的原典／作者版本；旧室内形态、元素及年度处方引用[证据审查](layout-rules.md)；本轮具体室内关系引用[Joey Yap／Ci Yuan／WOFS 及镜面 Cho 异议](sourced-interior-rules.md#室内规则的来源与分歧)，材料／颜色与器形分别引用 AFSI／FSI。用户明确另选的桌面现代 BTB 引用[作者规则](surface-rules.md)的 Anjie Cho、Tori McBrien。卦象及九星教学引用实际返回的古文转录／作者教材，生肖索引引用已登记二十四山表及生肖对应来源；这些索引不证明人物必然受影响。每条行动采用实际返回的来源，不把另一流派文章当这条规则的证明。来源记录只按实际保存的版本、定位、检索与散列字段交付，不为未保存的项目声称内容散列；AFSI 教材已于本轮取得同散列 PDF，材料定位以印刷23、25／PDF40、42页为准；用途与施用条件按[工位作者规则](workstation-authored.md)分别署名。来源可追溯不等于现实效力已验证。

交付后保留未解决项目、缺失事实和复核点。后续更正更新输入，维护同一 trace 与父 run；只解释不重算。物理调整是否落实、能否看见入口、是否有遮挡等可以核验，事业或财富改善不能由布局引擎确认。
