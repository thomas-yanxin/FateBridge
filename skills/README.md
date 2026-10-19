# Onda 咨询技能

Onda 按用户的问题组织 FateBridge 的计算与解释。引擎提供可复核的盘面与规则，技能负责选择当前主题、对象、时间范围和交付方式；用户只需说明问题与已知资料，无需先了解工具名或专业字段。

本页供咨询入口选择与技能维护使用。首次安装或注册 MCP 见 [Codex 使用指南](../docs/codex-guide.md)，工具与场景的区别见[核心概念](../docs/concepts.md)。

## 选择一个主题入口

默认处理这次问到的主题，不自动展开所有关联领域。专题综合主动评估有新增价值的多视角；简单单项或指定方法保持其范围。明确要求全面时由组合入口组织，追问复用已有相关结果。

| 用户关心什么 | 入口 | 交付重点 |
| --- | --- | --- |
| 自己的性格、天赋与做事方式 | [onda-mingge](onda-mingge/SKILL.md) | 相关特点、适用条件、来源与分歧 |
| 工作方向、岗位、晋升、跳槽、创业角色 | [onda-shiye](onda-shiye/SKILL.md) | 事业结构、阶段与实际工作选项 |
| 收入、消费、积累、回款、共同资金 | [onda-caiwu](onda-caiwu/SKILL.md) | 财务方式、时间变化与真实资金条件 |
| 恋爱、桃花、伴侣与婚姻相处 | [onda-yuanfen](onda-yuanfen/SKILL.md) | 单人特点、双方互动和时间层分开 |
| 学习、考试、深造、专业、留学 | [onda-xueye](onda-xueye/SKILL.md) | 学习方式、阶段与现实准备 |
| 原生家庭、六亲、亲子 | [onda-jiating](onda-jiating/SKILL.md) | 命主视角、家人本人和双人互动分开 |
| 朋友、团队、合伙、人际支持 | [onda-renji](onda-renji/SKILL.md) | 交往方式、分工与磨合，不代替信用判断 |
| 传统身心／中医文化解释 | [onda-jiankang](onda-jiankang/SKILL.md) | 盘内分类与传统对应，非诊断、非治疗 |
| 住宅、工位、布局与物件 | [onda-fengshui](onda-fengshui/SKILL.md) | 空间事实、作者规则、候选差异与条件 |

## 时间与指定方法

| 用户要求 | 入口 | 与主题的关系 |
| --- | --- | --- |
| 整体时运、人生阶段、给定候选时刻 | [onda-shiyun](onda-shiyun/SKILL.md) | 无主题限定时主持；事业或关系的时间问题仍由原主题主持 |
| 指定命盘、流派或技法 | [onda-xingpan](onda-xingpan/SKILL.md) | 尊重用户指定的方法，按实际主题读取结果 |
| 明确起卦或问事 | [onda-zhanbu](onda-zhanbu/SKILL.md) | 使用所选卜法；普通决定不自动起卦 |
| 多主题全面画像 | [onda-zige](onda-zige/SKILL.md) | 组合相关主题，多体系能力由各主题共享 |

共 13 个技能包（9 主题、3 服务、1 多主题组合）；机器场景另有独立的 `fengshui` 基础计算，共 14 项。REST 公开 86 个工具，MCP 公开 87 个工具，工具数不因主题重组而增加，实际范围见[算法覆盖](../docs/algorithm-coverage.md)。

## 共用参考如何分工

| 参考 | 负责什么 |
| --- | --- |
| [硬边界](_shared/safety-boundaries.md) | 在选法与计算前识别生死、临床诊断治疗、医疗择时等禁区 |
| [本轮范围与多视角选择](_shared/consultation-routing.md) | 识别主题、对象、任务与深度，避免扩大问题或重复取证 |
| [时间选择](_shared/timing-selection.md) | 选择阶段、年度与更细粒度，保留各体系真实边界 |
| [引擎调用](_shared/fatebridge-engine.md) | 输入合同、字段、错误、复现与完整结果交付 |
| [Onda 解读](_shared/onda-counsel.md) | 把实际依据讲清，区分传统解释与现实建议 |
| [结果交付](_shared/consultation-delivery.md) | 按问题选择短答、对照、时间线或完整解释 |
| [西占主题读取](_shared/western-topic-evidence.md) | 查相关配置及解释来源，避免冒称专项评分能力 |
| [西占深层证据](_shared/western-deep-evidence.md) | 按需读取古典点、朔望、力主、恒星、行星时和方向性关系证据 |
| [八字专题细问](_shared/bazi-topic-evidence.md) | 财库、财富结构、学业、六亲与子女等专项的实际字段和解释范围 |
| [时运技法任务卡](onda-shiyun/references/techniques.md) | 各技法的新增信息、选择条件、真实读取与追问复用 |

普通咨询按匹配技能读取所需参考，无需先读整个仓库。风水有独立的[咨询闭环](onda-fengshui/references/consultation.md)，事实、来源与动作条件在该目录分层维护。

## 发现与文件职责

每个技能包由以下文件协作，维护源位于本目录。

| 文件 | 用途 |
| --- | --- |
| `SKILL.md` | 适用问题、取证、读取与交付规则 |
| `agents/interface.yaml` | 直接文档化工具、资料、场景元数据与生成清单的来源 |
| `agents/openai.yaml` | Codex 的技能展示与发现配置 |
| `references/` | 仅在相应任务需要时读取的细则与来源 |

项目 `.agents/skills/onda-*` 指向 `skills/`；从软链接发现时，先解析真实目录再读相对引用。技能支持自动发现，也支持 `$onda-caiwu` 等显式调用。既有会话可能需重新加载技能，已运行 MCP 进程须重启才加载新代码与 Schema。

`required_inputs` 描述可用资料，不是把所有方法缺项合成一份必填问卷。实际必填项取决于所选工具 Schema。`FATEBRIDGE_MCP_SCENARIOS` 筛选实际公开工具，限制为单主题仍可包含其已声明的时间与其他视角，但不会自动调用整个清单。

## 维护与验证

使用锁定的 uv 开发环境。改工具说明或元数据后检查技能合同；改路由与共享规则后由脚本生成场景清单；接口变动时重新生成根调用合同，不手改生成区。验证步骤见[开发指南](../docs/development-guide.md#文档维护与验证)。

静态技能检查、真实 MCP 调用与独立模型对话分别报告；接口边界变动还须核对 REST、MCP 与 CLI。后台工具数量不作为咨询交付质量指标。

本目录随 Git 仓库按 Apache-2.0 分发，当前 wheel 不包含技能目录。回到[文档中心](../docs/README.md)选择接入或开发任务。
