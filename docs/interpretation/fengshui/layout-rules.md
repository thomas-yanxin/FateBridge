# 通用风水布局补充规则的证据与边界

[资料与来源](consultation.md) · [基础规则](rule-sources.md) · [室内两端关系](sourced-interior-rules.md) · [请求示例](../../examples/README.md)

`fengshui_assess` 的室内形态、元素目标及年度作者规则使用通用输入，不另设工位专用工具。规则数据位于 `src/fatebridge/data/fengshui/layout-supplements-v1.json`，记录作者、检索日期与版本；运行时离线使用规则，不访问外部网站。

本页核对三类补充规则的来源和排除范围；具体请求及输出分支见[工程说明](../../fengshui.md#布局室内形态与扩展输入)。镜照床、厨卫和梁管等明确两端关系另查[室内规则](sourced-interior-rules.md)，不由本页入口视野条件代替。

## 室内形态

[Tori McBrien在IFSG发表的控制位置文章](https://www.ifsguild.org/the-feng-shui-command-position/)给出床、桌、灶的入口视野与避开入口直线条件；作者自述采用 Black Sect。本实现将其记录为现代作者规则，未将该版本宣称为所有古籍或门派的统一峦头算法。镜面仅作为改善入口视野的条件选项。

[Karen Kingston的作者文章](https://www.clearspaceliving.com/blog/feng-shui-command-position/)支持床/桌的实体背靠与入口视野。两篇来源均未给出以米为单位的统一吉凶阈值，因此距离仅存为证据；观察缺失与照片候选保持不确定性。

版本 `indoor_command_authored_v1@1.1.1` 分别检查可见性、直线与背靠，不从“右后门”推出门冲。实体背靠条件不强加给灶。床头支撑的具体建议同时引用 McBrien 的 Practical Applications 段落，Kingston 提供一般背靠条件。所有结论仅覆盖已提供对象和所选作者条件。

## 五行目标与代表物

[Larry Sang/AFSI出版的《The Principles of Feng Shui》](https://www.amfengshui.com/wp-content/uploads/woocommerce_uploads/2013/12/tpofs.pdf)第六版（2004年7月）第三章，印刷页19–28（PDF第36–45页；材料重点印刷23、25／PDF40、42页），提供生/克/泄关系、实际元素和色彩的代表物；实际元素优先于颜色。木代表物限定健康活植物，处理木家具不自动作为该版本的木调节物；水代表物须清洁且流动。土类颜色中的 `tan` 按浅棕褐色标明，不扩大为所有棕色。

`afsi_element_balance_v1@1.0.1` 仅将明确目标绑定到已算五行，再返回代表物候选；不将个人命卦当喜用神，不从普通凶星逻辑推导灶座处方，不给数量、重量、概率或现实效果大小。加入元素对同一对象其他层的关系分列。代表物描述不确认现场已经清洁、运行或适用；已提供具体材料及施用事实时，由[既有材料条件](workstation-authored.md)单独核对。

## 年度作者规则

[Adelina Pang作者发布的2026指南](https://adelinapang.com/wp-content/uploads/2025/09/@2026-Horoscope-Forecast-Fengshui-Guide-by-Adelina-Pang-1.pdf)PDF第35–36与37–38页，分别给出南宫5、西北宫2的金元素候选与避火；页码均从1开始。`pang_2026_annual_v1@1.0.1` 仅选取这两项，以已有年度盘的有效年和对象所在宫位为条件。其他年份、其他星和面对方向均不能触发本版本方案。

原文PDF第40页在南宫五黄段落出现西南位置，内部不一致；旧登记误写为第39页，现已更正。该段盐水配方未采用。健康/灾害/财富预测、盐水数量及复杂物件强度均未实现。

[Sean Chan明确反对以摆件作为化解](https://www.masterseanchan.com/blog/what-feng-shui-cure-really-is/)，与AFSI/Pang的物件路线存在立场分歧。程序保留选定版本及该分歧，不把作者处方合成全门派共识。
