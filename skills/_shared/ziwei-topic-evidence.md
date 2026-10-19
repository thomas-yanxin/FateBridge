# 紫微本命与动态结果的证据读取

先按本轮主题和[共享时间选择](timing-selection.md)取证。本页约束的是对象身份和计算连接，不另造事业评分器；有已返回连接时直接解释，不为同一连接重复排本命。

## 三种宫位身份

| 实际数据 | 对象身份与能回答的部分 | 不能改称 |
| --- | --- | --- |
| `ziwei_birth.palaces` 每项 `name/ganzhi/stars_detail`；命身另看 `ming_gong/shen_gong` | 本命十二宫；`stars_detail.name/brightness/mutagen` 是本命星、亮度与本命四化 | 目标年份的流年官禄／财帛等功能宫 |
| `ziwei_horoscope.scopes` 的 `scope/scope_palace_role/natal_palace_name/branch/palace_ganzhi` | `scope_palace_role=ming_palace_activity_index` 时，是该运限命宫活动索引所临的本命宫；旧 `palace_name` 是兼容名 | 该运限同名功能宫；如所临本命迁移宫不等于已完整审查流年迁移宫 |
| 该运限官禄等其他功能宫及完整旋宫表 | 仅在实际合同明确提供时才可读取 | 当前没有输出时，不能由活动索引、宫序或外部软件手工补出并称引擎结果 |

普通动态首轮取实际合同的 `analysis_context`、`birth_context`、`ziwei_horoscope.interpretation_scope/nominal_age/calendar_rules/scopes`。`scopes` 数组整体取回，再按 `scope` 选本次需要的大限、流年等层；不编 `scopes.流年` 或数字索引投影。核对 `analysis_context.context_role=target`、`analysis_datetime` 及其时区；`birth_context` 用于出生处理核对。旧部署若仍把出生日期放在 `analysis_context`，不能将出生日期冒充目标回执；按实际可核验目标范围说明，不把缺回显解释成整张盘无用。

上述 `birth_context` 是动态接口新增字段；本命 `ziwei_birth` 的出生回执仍是 `analysis_context/person_info`，不能因两工具资料相似而复制投影路径。

## 四化连接先认星，再认宫

当前每层 `mutagen` 是该层天干的四化星名；`mutagen_natal_links` 每项明确 `transformation/star/natal_palace_name/natal_palace_ganzhi/natal_branch/natal_star_label/natal_star_brightness/natal_mutagen`。这是动态标记连接本命星的落宫，优先使用引擎给出的连接，不重复调用本命。解释需要更多本命配合而已有本命盘时，再复用 `palaces[].stars_detail`；没有连接的旧部署可按实际星名核对已保留本命表，不能猜落宫。

- 示例读法：本命官禄有天机，目标流年 `mutagen.化科=天机` 且对应连接落本命官禄，可以说“该流年化科标记关联到本命官禄中的天机”。这不等于“流年官禄宫化科”。
- 本命 `natal_mutagen` 与流年 `transformation` 分开，不能把年度四化永久写入本命。某星没有连接时说明这一项未连接，不能假定另一个宫位。
- “化科便晋升”“化忌便不得转职”不是这些字段的结论。星曜、亮度、四化及相关宫位的传统含义需另有可靠作者／规则来源；有来源时可给与所问相关的条件式解释，未核对时保留为计算连接，不冒充已核实原典。

## 专题解释与新增价值

事业方向可读实际本命官禄、命身相关星曜配置；目标年度则说明大限背景、该年标记关联哪些已确认本命对象。来源查询可使用 `knowledge_registry/knowledge_read` 或已核验作者文本，记录作者、版本、章节／页码及适用范围。排盘与外部软件一致，只核验所选口径下的计算；它不是星性、现代职业类比或现实预测有效性的出处。

用户明确要求原典版本与页码的审查中，在线转录的卷／章节定位不能冒充书影页码；未核到所选版本和页码的解释只列作未验参考，不作为已验收的传统主证。也不能从单星象意补出未查证的“运限四化连接本命宫后如何断事”组合规则。此时仍交付计算连接、已核实的其他依据和独立现实建议，不靠增加调用填补来源缺口。

把“返回事实”“来源解释”“现实建议”分开：例如先给出年度四化关联本命官禄的事实，只有查到相应解释规则后才讨论它怎样联系本次工作任务；面试材料、岗位授权、薪资和交接计划作为独立现实条件。没有相关解释来源时，不用别的主题象意或笼统吉凶填空，仍可交付已有八字／其他有据视角。

第二方法应补充原先没有的主题结构、时段条件或真实分歧；相同出生数据共享历法输入，不能当作独立统计印证。删除紫微会丢掉一个新字段，只能证明信息增量；咨询增益还要看它是否改善本次判断及表达。
