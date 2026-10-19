# 通用风水布局补充规则的证据与边界

[场景技能](../SKILL.md) · [基础规则](rule-sources.md) · [室内两端关系](sourced-interior-rules.md) · [请求示例](../../../docs/examples/README.md)

`fengshui_assess` 的室内形态、元素目标及年度作者规则使用通用输入，不另设工位专用工具。规则数据位于 `src/fatebridge/data/fengshui/layout-supplements-v1.json`，记录原始文件 SHA-256、作者、检索日期与版本；运行时离线使用规则，不访问这些网站。

本页核对三类补充规则的来源和排除范围；具体请求及输出分支见[工程说明](../../../docs/fengshui.md#室内形态与有条件物件规则)。镜照床、厨卫和梁管等明确两端关系另查[室内规则](sourced-interior-rules.md)，不由本页入口视野条件代替。

## 室内形态

[Tori McBrien在IFSG发表的控制位置文章](https://www.ifsguild.org/the-feng-shui-command-position/)给出床、桌、灶的入口视野与避开入口直线条件；作者自述采用 Black Sect。本实现将其记录为现代作者规则，未将该版本宣称为所有古籍或门派的统一峦头算法。镜面仅作为改善入口视野的条件选项。

[Karen Kingston的作者文章](https://www.clearspaceliving.com/blog/feng-shui-command-position/)支持床/桌的实体背靠与入口视野。两篇来源均未给出以米为单位的统一吉凶阈值，因此距离仅存为证据；观察缺失与照片候选保持不确定性。

版本 `indoor_command_authored_v1@1.1.0` 分别检查可见性、直线与背靠，不从“右后门”推出门冲。实体背靠条件不强加给灶。所有结论仅覆盖已提供对象和所选作者条件。

## 五行目标与代表物

[Larry Sang/AFSI出版的《The Principles of Feng Shui》](https://www.amfengshui.com/wp-content/uploads/woocommerce_uploads/2013/12/tpofs.pdf)第三章，印刷页19–28（PDF第36–45页；材料重点印刷23、25／PDF40、42页），提供生/克/泄关系、实际元素和色彩的代表物；实际元素优先于颜色。木代表物限定活植物，处理木家具不自动作为该版本的木调节物。

`afsi_element_balance_v1@1.0.0` 仅将明确目标绑定到已算五行，再返回代表物候选；不将个人命卦当喜用神，不从普通凶星逻辑推导灶座处方，不给数量、重量、概率或现实效果大小。加入元素对同一对象其他层的关系分列。

## 年度作者规则

[Adelina Pang作者发布的2026指南](https://adelinapang.com/wp-content/uploads/2025/09/@2026-Horoscope-Forecast-Fengshui-Guide-by-Adelina-Pang-1.pdf)PDF第35与37页，分别给出南宫5、西北宫2的金元素候选与避火。`pang_2026_annual_v1@1.0.0` 仅选取这两项，以已有年度盘的有效年和对象所在宫位为条件。其他年份、其他星和面对方向均不能触发本版本方案。

原文第39页在南宫五黄段落出现西南位置，内部不一致；该段盐水配方未采用。健康/灾害/财富预测、盐水数量及复杂物件强度均未实现。

[Sean Chan明确反对以摆件作为化解](https://www.masterseanchan.com/blog/what-feng-shui-cure-really-is/)，与AFSI/Pang的物件路线存在立场分歧。程序保留选定版本及该分歧，不把作者处方合成全门派共识。
