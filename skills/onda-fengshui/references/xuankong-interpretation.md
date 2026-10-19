# 玄空宅盘条件解读：来源、覆盖与限制

[场景技能](../SKILL.md) · [历史宅盘规则](xuankong.md) · [启用示例](../../../docs/fengshui-xuankong.md#有限解释调用与复现) · [工位用途](workstation-authored.md)

`xuankong_conditioned_v1@1.0.0` 是显式启用的有限解读层，读取已有运山向宅盘，不更改 `xuankong_zhongzhou_v1` 的起盘规则。它补充山向星的五行关系、评价时运、外局存在条件及床／门的取用角色；不把排盘结果升级为完整住宅吉凶判断。

先核对[可计算范围](#可计算范围)，需要调用时按[启用与读取](#启用与读取)选择分支。没有启用本层时，数字宅盘仍可返回；仅有数字不能代替本页的外局和用途条件。

## 来源核对与版本选择

2026-10-15 重新核对以下作者／出版方页面。网页传录和作者自刊资料分别保留来源性质，不能统称为经认证的《中州派玄空学》印本。

| 来源 | 性质、定位 | 本次只采用的内容 |
| --- | --- | --- |
| [玄霖易学《第二篇 玄空理气入门3》](https://xuanlinyi.com/article_detail?id=301281) | 与起盘规则 X2 同系列的网页传录；页面署“笔者”，引述王亭之，未核实原作者及印本版次 | 当运星的基本定义；当旺山星与山形、向星与水形的条件关系；床取山盘、门及走动路线取向盘；形峦和二星配合仍须另外核对 |
| [Kartar Diamond：Excerpt from the Mountain Dragons and Water Dragons Case Study](https://fengshuisolutions.net/excerpt-from-the-mountain-dragons-and-water-dragons-case-study-by-kartar-diamond/) | 作者本人网站，2025-04-26 | 山星／向星是盘中角色，不能与星自身五行混淆；先核时令，再看形态与用途；作者明确不同学校有不同处理方法 |
| [Kartar Diamond：Feng Shui Interpretation of Yin Rooms and Yang Rooms](https://fengshuisolutions.net/feng-shui-interpretation-of-yin-rooms-and-yang-rooms-by-kartar-diamond/) | 作者本人网站，2024-05-05 | 睡眠与入口等活动用途应区分；当运山星和向星分别作为睡眠、入口取用的依据。本版本只采用床和门，不扩展为所有工作桌规则；文中九运“2024–2044”的端点不用于定运 |
| [American Feng Shui Institute：FS351—Day Selection, Class 2](https://www.amfengshui.com/wp-content/uploads/2014/09/fs351.pdf) | 出版方 PDF，2006；Larry Sang 传授、Lorraine Wilcox 撰写、Hermann Urkauf 编辑；印刷第56页／PDF第56页 | 星数与五行的对应表；不采用该节求子、疾病及吉凶断语 |
| [Larry Sang／American Feng Shui Institute：The Principles of Feng Shui](https://www.amfengshui.com/wp-content/uploads/woocommerce_uploads/2013/12/tpofs.pdf) | 已有规则来源 E1；第三章，印刷第19–28页／PDF第36–45页；本轮已取得同散列 PDF，五行材料重点印刷23、25／PDF40、42页 | 五行生、克及泄的机械关系，不由“相生”自动推论吉利 |

第一项与现有中州网页选版相连；后两位作者／出版方提供独立核对，不代表他们的全部理论与中州派相同。实现采用明确标注来源的共同有限条件，不混入其他作者的换运、摆件、疾病或灾害结论。

## 可计算范围

### 山向星的有序五行关系

星数映射为：1水；2、5、8土；3、4木；6、7金；9火。先识别山星和向星，再输出比和、山生向、向生山、山克向或向克山。

这一映射可机械覆盖全部81个有序数对，但只覆盖五行结构。山1向4与山4向1的方向不能颠倒；数字相加为十也不能直接获得“合十吉局”。本版没有81对断事表，不把一四断成升学成功，也不把二五断成疾病；五黄仍按土处理，不使用借星或隐组合替换其本来五行。

### 评价时运与历史宅运分开

`interpretation.current_period_number` 与非空 `period_evidence` 成对输入。当前评价时运不能由历史竣工运、年星入中数或系统日期暗中补齐。星数与明确评价时运相同，标记 `current`；其余标记 `not_current`，只表示不是本运当令星，不等于凶星。

同源传录另有生气、退气、辅星及难星等细分，包含多重条件与例外。本版没有实施这些分层；不能把 `not_current` 擅自细分为衰死，或据此拒用一个房间。

### 外局存在条件

`external_forms` 以全宅中心的八方向分别记录 `mountain_present`、`water_present`、`observation_basis` 与 `evidence`。每项可以为真、假或未知，但每条观察至少有一项明确的真／假。山和水可同时存在；未提供不表示不存在。

这里只处理已经明确分类的外部山形、水形存在事实，不沿用金锁玉关的砂水分类，不把椅背、墙、桌面植物或“允许移动”转换为外局。照片观察只形成候选，须保留待确认状态。中宫不适用全宅外部方向条件。

当令山星检查该宫外部山形是否存在，当令向星检查水形是否存在。存在只满足一项必要的存在条件；不存在只表示未满足该项，不能反推出相反形势。尤其“无山”不等于“见水”，“无水”不等于“见山”。山水的距离、规模、遮压、环抱、流速、冲射与先后次序仍未计算，因此不输出综合吉凶或整体适用结论。

### 用途按落宫检查

床的位置使用该宫山星，门的位置使用该宫向星，返回其五行数对、当令与外局条件。面向方向不能代替物件在全宅中的位置。只有床头朝向而没有床的位置时，保留缺失层；桌和灶用途明确标为本版未覆盖。

用途检查不是自动选房、搬床或施工建议。即使某项存在条件满足，也不能越过形态质量、使用者需求、实际可行性和其他已知冲突。

书桌工作／学习用途在独立 [workstation_activity_authored_v1](workstation-authored.md) 中显式启用，读取 `layout_analysis.workstation_analysis`；旧 `xuankong_conditioned_v1` 的桌未覆盖回执继续保留，不能混为同一版本。用途参考按落宫取向星角色，不等于要求摆真实水体。

## 启用与读取

聚合布局使用 `fengshui_assess`，选择 `xuankong_natal`，启用 `analyze_layout`，在已有 `xuankong` 宅盘请求中显式提供 `interpretation`。咨询摘要在原共享首轮 `fields` 之外追加 `layout_analysis.natal_interpretation`；独立宅盘则读取 `layers.xuankong_natal.interpretation`。新增分支为显式启用，未请求解释时不要在严格投影中选择不存在的分支。完整导出首次 `fields=null`，超过默认预算时从 `result_delivery` 读取同一 run。

完整请求仍须保留用户确认的住宅、历史定运、物件位置与证据。磁北误差导致多个宅盘时逐候选解释，不挑选最有利盘。资料核对见 [历史宅盘](xuankong.md)。示例或默认值不能作为用户资料。

`status` 继续表示原始排盘是否齐备；`coverage.natal_interpretation_status`、`natal_interpretation_missing_inputs` 和 `requested_analysis_status` 记录所请求解释是否齐备。布局聚合另把解释缺失合入布局状态。`complete` 仅表示有限规则所需资料已核对，`rule_coverage_status=limited` 仍保留未覆盖范围；已确认条件不满足不是缺失输入。

## 证据边界与后续范围

每项结果保留规则 ID、来源 ID、输入事实及作用域，供规则核对和后续解释。完整宅盘、年盘、个人匹配、室内形态和本层条件分别呈现；不会相互抵消、合成分数或自动生成补救处方。

本版未覆盖81对专门断语、合十成局、城门、零正神、七星打劫、反伏吟、特殊五黄借星解释、完整峦头质量、年盘叠加断事、自动房间规划或现实效力验证。新增这些能力须逐项确定作者／版本、触发条件、可观测输入与独立样例，不能仅凭常见口诀添加一张吉凶表。
