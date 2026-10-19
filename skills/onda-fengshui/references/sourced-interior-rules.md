# 有来源的室内关系、材质与器形规则

[场景技能](../SKILL.md) · [资料核对](consultation.md) · [工位与材料条件](workstation-authored.md) · [工程接入](../../../docs/fengshui.md)

本文说明无方位具体关系审查，以及五行、器物与方法细节的有来源范围。具体规则保留署名作者与版本，不将现代作者建议包装成经典原文或所有门派共同禁忌。计算能核对所选规则及确认事实，不能据此预言疾病、财富或关系结果。

按问题查阅：[两端关系与角色](#两端关系与单对象属性)、[作者来源与分歧](#室内规则的来源与分歧)、[属性输入](#单对象属性输入)、[代表物资格](#器形参考与代表物资格)、[结果和动作状态](#结果候选与动作边界)。纯象意表另见[与方法细节的区别](#与方法细节的区别)。

这些输入继续使用 `fengshui_assess`，不增加厨房、卧室等专用工具；可以 `methods=[]` 独立审查已提供的室内关系和属性，无需个人生辰、宅向或虚构宫位。若同时请求飞星／金锁的实际落宫，仍须分别满足方位、户型对齐、中心及楼层门槛。

## 两端关系与单对象属性

`environmental_context.interior_relations[]` 的字段为 `relation_id`、`source_object_id`、`target_object_id`、`kind`、`present`、`observation_basis`、`evidence`。源与目标是实际对象，不能仅给房间名称就推断其用途。对象角色放 `environmental_context.objects[].role`；已有明确床、桌、灶用途可以沿用，普通 door 不自动变成主门或卫生间门。

关系类型表达明确的物理条件，不能相互替换：相邻不等于正对，门对厨房不等于门正对灶台，物品呈尖形不等于实体尖角指人，镜子存在也不等于镜面反射床或灶。只传当前 Schema 允许且已观察到的 `kind`，其他描述保留原话和未支持范围。

本版明确的 11 种角色为 `main_entry_door`、`bathroom_door`、`stove`、`sharp_corner`、`pillar_corner`、`bed`、`desk`、`exposed_beam`、`pipe`、`toilet_wall`、`mirror`。`pillar_corner` 限实体柱角，可作为尖角来源；普通尖角不能反向升级为柱角。关系的源／目标角色按下表配对，不因同处一个房间就自动成立：

| `kind` | 源 → 目标及必须确认的关系 | 规则／署名来源 |
| --- | --- | --- |
| `main_entry_door_faces_bathroom_door` | 主入户门 → 卫生间门，明确直接对齐 | IR1／Joey Yap |
| `bathroom_door_faces_stove` | 卫生间门 → 灶，明确正对灶台 | IR2／Ci Yuan Feng Shui |
| `sharp_corner_points_at_stove` | 实体尖角 → 灶，明确尖角指向灶 | IR3／Ci Yuan Feng Shui |
| `pillar_corner_points_at_bed` | 突出的实体柱角 → 床的实际睡卧位置；不含普通家具角 | IR4／WOFS Bedroom |
| `sharp_corner_points_at_desk` | 实体尖角 → 书桌实际坐者位置 | IR5／WOFS Desk |
| `exposed_beam_above_stove` | 实际梁体 → 灶，明确在其占用区域上方 | IR6／Ci Yuan Feng Shui |
| `exposed_beam_above_bed` | 外露重梁 → 床，明确在睡卧区域上方 | IR7／WOFS Bedroom |
| `pipe_above_stove` | 实际管道 → 灶，明确跨越正上方区域 | IR8／Ci Yuan Feng Shui |
| `bed_headboard_against_toilet_wall` | 床 → 墙另一侧实际便器所在处的共墙，床头明确贴靠 | IR9／WOFS Bedroom |
| `mirror_faces_bed` | 镜面 → 床，明确可反射睡卧区域 | IR10／WOFS Bedroom；另保留 Cho 异议 |
| `bed_above_stove` | 床 → 灶，明确床高于灶且睡卧区域与灶垂直投影重叠 | IR11／WOFS Bedroom |
| `stove_back_against_toilet_wall` | 灶 → 墙另一侧实际便器所在处的共墙，灶背明确贴靠 | IR12／WOFS Toilet Wall |

`present` 必须显式提供，可为 true、false 或 null。null 表示该关系尚未确认；用户／测量确认的 false 只说明本条关系不成立，不证明全部室内关系都无问题。照片依据 `image_observed` 的 true、false 均保留候选状态，不能用图片中的“没看到”作为确认不存在。每条关系独立保存依据，不由行动许可、目标或其他对象事实补齐。

IR1 不将“从门口能看见卫生间”当直接对齐；作者强调的不足十英尺情形也不转成统一吉凶阈值。IR4 须确认实体柱角，不泛化为床边任意家具尖角。IR6～8 的梁与管线不凭天花造型、灯具或同室存在而成立，不生成切梁、移管等工程动作。IR9／12 的 `toilet_wall` 须确认墙另一侧是实际便器所在处，并确认床头／灶背贴靠；任意卫生间隔墙、邻室或同层均不足以成立。

## 室内规则的来源与分歧

运行时读取 `interior_authored_relations_v1@1.0.0`，逐项规则为 IR1～IR12；来源登记在 `src/fatebridge/data/fengshui/interior-relations-v1.json`，包含实际检索版本与原文定位。下列作者／机构分开归属，不将 WOFS 的编辑文章自动署名给 Lillian Too：

| 来源 | 本次定位与范围 |
| --- | --- |
| [Joey Yap：Feng Shui 101 — Water closet](https://joeyyap.com/upcoming/media-details.asp?mid=1340) | 官方存档 2010-01-26；主门与厕门直接对齐段。IR1 无已登记非结构动作，不自动建议拆门、加屏风或购买物件 |
| [Ci Yuan Feng Shui：Unrevealed Feng Shui Cures, Tip #1–10](https://cyfs.sg/wp-content/uploads/2021/05/Unrevealed-Feng-Shui-Cures-Tip-1_10.pdf) | 2015-01 第二版；PDF 第 11 页 Tip #8 续段中的灶位关系，对应 IR2／3／6／8 |
| [WOFS：Revitalize Your Bedroom](https://www.wofs.com/revitalize-bedroom-energy/) | 2026-10-15 检索版，发布日期未核实；第 9 节卧室位置／床位条目，对应 IR4／7／9／10／11 |
| [WOFS：7 Quick Tips to Bring You Career Success](https://www.wofs.com/7-quick-tips-career-success/) | 2026-10-15 检索版，发布日期未核实；第 1 节突出尖角与第 2 节桌角，限 IR5 工位实际坐者关系 |
| [WOFS：Aunt Agga Issue #129](https://www.wofs.com/aunt-agga-issue-129/) | 第 129 期检索版，发布日期未核实；灶背共墙另一侧为便器的具体问答，采用 IR12 的窄关系 |
| [Anjie Cho：Q&A Sunday — Mirrors in the Bedroom](https://www.anjiecho.com/holistic-spaces-blog/2018/7/8/q-a-sunday-mirrors-bedroom) | 2018-07-08 作者文；保留 BTB 对卧室镜面的不同口径及入口视野用途，作为 IR10 的异议参考 |

镜照床的 WOFS 提醒与 Cho 的 BTB 口径在 `finding.method_disagreements` 分列；异议不自动取消 WOFS 条目，也不表示用户已选择 BTB。不得把镜子本身视作所有方法共同禁忌，更不能用镜面补视野建议抵消其他已确认关系。

### 单对象属性输入

`environmental_context.material_facts[]` 独立记录 `fact_id`、`object_id`、至少一项 `material|shape|colour`、`observation_basis` 和 `evidence`。可另给 `plant_alive`，但仅用于明确的 `living_plant`；可另给 `element_use`，表达用户明确询问这件物品能否充当某种元素代表物。

材质、器形、颜色是不同观察。不能由圆形判金属、绿色判活植物、陶瓷色判真实陶瓷；同一对象有多条事实时，各自依据和确定程度分别保留。未知属性用允许的 `unknown` 或省略，`element_use` 不能取代实际属性。

同一对象的同一属性不重复登记；材料、器形和颜色可分成不同事实，分别保存用户确认或图片依据。不同属性事实可以各自携带同一明确 `element_use`，但同一对象不能同时声明互相矛盾的代表物用途，结果也不自动跨事实拼接。不能为了把图片属性升级为确认，把它与另一项已确认属性合并成同一条已确认事实。

材料接受 `wood|processed_wood|living_plant|metal|stone|ceramic|glass|plastic|textile|water|mixed|unknown`；器形接受 `columnar|triangular|square|round|wavy|irregular|unknown`。颜色按当前枚举记录，不能因为颜色已知就确认未提供的材质。具体取值仍以连接中的完整 Schema 为准。

IR5 与旧工位尖角观察另保留 WOFS／Joey Yap 的作者分歧：后者不把普通小物／家具角一概当煞。不同口径分列，原 WOFS 提醒不自动取消；不从“尖形物件”推“实体尖角直指坐者”。详见[工位来源边界](workstation-authored.md)。

## 器形参考与代表物资格

器形的五行对应属于署名教学参考；它不自动证明该物件能作某元素的调节物。材料／颜色资格使用 `sourced_material_representation_v1@1.0.0` 并保留条件和异议。例如 [Larry Sang／AFSI《The Principles of Feng Shui》](https://www.amfengshui.com/wp-content/uploads/woocommerce_uploads/2013/12/tpofs.pdf)第三章印刷第 19–28 页／PDF 第 36–45 页的既有规则以健康活植物作木代表物，处理木家具不作为该版本的木调节物；不能因木椅呈柱形或涂绿色就消除这一材料限制。本轮已取得同散列原始 PDF，材料重点定位为印刷23、25／PDF40、42页。附加施用条件、目标绑定和 AFSI／Diamond 的柜内金属异议见[工位作者规则](workstation-authored.md)；资格不认证剂量或摆放位置。

[Feng Shui Institute《The Five Elements – Wu Xing》](https://www.feng-shui-institute.org/Feng_Shui/fiveelements.html)的 Water／Wood／Fire／Earth／Metal Energy 段落提供本版器形参考：

| 明确器形 | 所选 FSI 版本的元素参考 |
| --- | --- |
| 柱状／高直 | 木 |
| 三角形 | 火 |
| 方正低平 | 土 |
| 圆或曲线形 | 金 |
| 波浪形 | 水 |

这是 FSI 器形教学，与 AFSI 材料／颜色资格分别保留；不采其人格、健康或物理学类比，也不将三角形直接判为指人的尖角。`irregular` 及未知器形不强配元素。

`element_use=wood_remedy|fire_remedy|earth_remedy|metal_remedy|water_remedy` 只表示代表物资格问题，不表示用户命盘喜用、不表示房屋当前缺或需要该元素。资格核对不新增位置、不推荐任何宫位，也不确认数量、重量、效果或 ready；如需具体元素调节，仍走绑定已计算对象／方法／作用域的 `element_adjustments`，并保留跨层关系和实际执行条件。

材料结果中的 `material_eligibility` 与 `colour_eligibility` 分开。例如处理木家具在木代表物问题上为 `excluded_by_selected_author`，若用户确认绿色并明确询问其颜色替代资格，可另得到颜色替代匹配；不能改写成材料已获认可。资格按每条 fact 已提供的属性与 `element_use` 判断，同一对象其他事实不自动拼接；一条仅确认绿色但未问代表物用途的事实仍是参考。照片属性、显式 unknown、活植物生死未确认或资格问题缺材料／颜色时，保留待确认；只有器形时不拿它替 AFSI 材料解答。玻璃、塑料或混合材料没有登记用途时不硬配元素。

## 结果、候选与动作边界

只在提交了对应输入时读取 `layout_analysis.interior_analysis` 或 `layout_analysis.material_analysis`；未提交时这些路径可以不存在，不能无条件加进 `strict_fields=true` 的首轮投影。所有风水说明仍保留 `rulesets` 与 `rule_trace`，按具体结果交付本次作者、版本、来源及适用范围。

室内关系 findings 的状态分别为 `authored_caution`（已确认关系成立的作者提醒）、`not_present`（已确认不成立）、`needs_confirmation`（显式未知）或 `candidate_only`（照片候选）。具体 `rule_id`、`predicate`、`exceptions` 和 `method_disagreements` 保留适用范围及分歧。新关系动作只会是 `blocked` 或 `conditional_option`，本模块不确认新位置几何／可容纳条件，因此不返回 ready；没有登记的非结构动作则明示 `no_registered_nonstructural_action`，不能为凑建议编搬改方案。

照片候选且 `present=true` 时，`conditional_interpretation` 提供“若现场确认该关系成立”的作者解释和条件式建议，保留规则及来源；不改写原 `interpretation`、事实确认和动作状态。`present=false|null` 不生成成立关系的提醒，已明确禁止的搬转不列入条件式建议。普通解释可先使用这些依据，落实方案前再确认关系、许可和实际空间。

材料结果保留原始事实、`material_reference`、`shape_reference`、`colour_reference`、分别的资格状态及缺失项。`placement_suitability=not_assessed`、`action_required=false` 说明这里只答属性与资格问题；未请求 `element_use` 时为纯参考，不把它计成新的摆放规则。

规则发现与动作门槛分别读取。确认某关系与所选作者规则相反，不证明家具能搬、能转或可以新增；图片候选和未知关系也不能产生可立即执行的结论。被禁止的动作保留 blocked 并清空该动作的执行追问，现状事实的不确定性另行保留。普通通风、卫生、消防和通行建议单列现实／工程理由，不冒充传统规则计算。

旧 `FormObservation.sharp_corner_points_at_user` 仅标识使用座位，没有尖角源物件 ID：其行动只分座位搬位与新增叶状屏障，分别检查目标座位的许可，不能凭此生成搬转未知来源物件的动作。新双对象关系可以准确标识两端，但动作仍须核对实际执行对象和相应许可，不能将一端的许可扩到另一端。

`layout_constraints` 可引用已登记的环境对象，各动作按自己的 `object_id` 和 `location|facing` 操作检查许可。原作者明确搬移的采用范围仅 IR2（Ci Yuan，PDF 第 11 页）、IR5（WOFS 工位第 1 节，退出尖角线）和 IR12（WOFS 第 129 期，灶搬位）。其余已登记动作是为改变明确关系提出的条件工程候选，不能归为作者明示处方；`action_basis` 在实际动作中交付。所有动作均不保证化解或现实效果；IR1 没有已登记非结构动作，不另编方案。

### 候选方案重核

候选在 `layout_alternatives[].environmental_context` 中提供独立新关系／属性。镜面、尖角源等方案可只给该上下文，但其中至少有一条涉及候选对象的新关系，不为它伪造床／桌／灶 `placement`。移动关系任一端都须以相同 kind、原源和目标重核，不能因另一端固定就沿用旧关系；每项已审条件须继续确认或明确否定，省略、换一种关系或只改变标签均不能视作已解决。关联属性按原材料／器形／颜色等粒度重核。其他固定对象和楼层事实保持其原作用域，许可与 `physically_feasible` 也不替代新关系证据。

固定关系端已有的楼层事实即使在候选省略，仍保留用于跨层关系校验。目标改换楼层或空间作用域须声明 `changes` 含 `location` 并核对搬位许可，不能仅声明转向。已确认的材料、器形、颜色及 `plant_alive` 布尔不随搬转改变；不能通过旋转让已确认非存活植物变存活。原照片或显式未知属性可以进一步确认，实际事实更正则替换现状并重算受影响输入。

候选输出自己的 `interior_analysis/material_analysis`；逐条比较的 `comparison_scope` 分别限明确关系判据及来源限定的代表物资格，不扩为罗盘判定、完整组合吉凶或现实效果。

## 与方法细节的区别

`method_details` 的 `expert_fengshui_methods_v1@1.1.0` 继续是 `reference_only`。先读 `mapping_boundaries`，再按结果所在体系查表：

| 路径 | 实际用途与边界 |
| --- | --- |
| `palaces[方向]` | 固定方区宫数、卦与五行；不表示当年到星 |
| `flying_star_references[星数]` | 按实际已算年／运／山／向星数查一至九星五行、署名主题及有限职业例；五黄不编本卦／家庭身份 |
| `cross_text_trigram_symbols[卦名]` | 古文人物／器物词类，只是本卦象意参考，不推实际居住者或家具摆位 |
| `bazhai_you_nian_references[星名]` | 八宅游年星自身五行，与同名紫白星分开；例如两套贪狼不能套同一五行 |
| `object_observation_references` | 古代器物词与现代家居观察提示分列，仍须确认材质、器形、用途与关系 |
| `methods[方法].application_references` | 飞星角色层、金锁形态、八宅门床灶用途的有限解释；现代灶具火口不由旋钮／电线猜测 |
| `sand_water_reference.form_condition_references` | 高度／逼近／断续、实际水流／道路关系、树木及院落范围的署名观察要求；不实现二十四山细断或数值阈值 |
| `material_shape_reference` | 上述 AFSI／FSI 独立参考；无实际属性时不产生资格结论 |

补充来源以实际记录的转录版本或作者教材为准：

| 来源 | 采用内容与明确限制 |
| --- | --- |
| [《梅花易数》卷一固定转录版](https://zh.wikisource.org/w/index.php?title=梅花易數/卷一&oldid=2690596) | oldid=2690596，2026-04-09 版本；八卦万物属类的人物／静物词类。未校勘纸本，不导入先天卦数、起卦、体用或职业预测 |
| [《沈氏玄空学》卷二](https://www.diancangwang.cn/xuanxuewushu/f6f37803664b/34f0e0aa12ff.html) | 2026-10-15 核对转录；“论四十八局”“论上山下水到山到向”“论三星五吉”，限区分固定宫、卦名与山／向临星，不扩成完整组合断语 |
| [Joey Yap：Feng Shui That Works](https://www.joeyyap.com/fstw/%5BJoey%20Yap%5DFengShuiThatWorks1.pdf) | 2018 教材 Step 3，印刷第 8 页／PDF 第 9 页原图；逐星教学主题，不使用示例 2018 方位当当前方位 |
| [Joey Yap：Annual Flying Stars Report 2009 样本](https://masteryacademy.com/estore/images/Products/report/AnnualFlyingStarsReport-Sample.pdf) | 第 9 页四绿学术／研究／写作例；第 10 页一白书房例；第 20 页三碧运动／活跃工作／手工职业例须保留山向 4–6 加年 3 组合。历史方位不用于当前，其他现代职业未覆盖 |
| [陈益峰：《金锁玉关二十山砂水》原文和注解](https://www.chinavalue.net/article/2015/6/9/1178679.html) | 署名整理，2015-06-09；网页标题“二十山”而正文为二十四山，采用 1.1／3.2／4.1 的形体、水路和树木观察提示，不认证传承、不实现二十四山细断或验应 |

署名九星主题及有限职业例子不是现代职业适配测试。引用某星组合中的作者例子必须保留该组合与用途，不能抽成单星永久吉凶或职业预测；没有登记的职业不补造。古代角色与现代作者职业例分别归属，也不能将跨文本词类当作三法共同规则。

金锁砂水、玄空外部山水、普通材质器形和室内背靠各自确认，不能彼此代填。具体关系规则、代表物资格、方法象意和现实建议分别交付，避免把参考说明当成新算出的摆放处方。
