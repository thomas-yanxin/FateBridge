# FateBridge · 场景咨询 Skills

FateBridge 引擎里有 80 多个命理、占术和占星工具。这个目录把它们按用户真正会问的出口重新组织成一套场景 Skill。

**计算交给 FateBridge 引擎，解读交给 Onda。** 每项 skill 围绕用户的问题组织盘面、阶段变化、双方差异或空间规则，让人看清依据和可参考的安排。工具数量不是交付目标。

- 所有计算都由 FateBridge 完成。已连接时优先 MCP，本地后备用 `python3 -m fatebridge.cli`；干支、排盘、合婚分数不交给 AI 手算。计算可复核、一致，不等于现实预测已验证。

## 用户能拿到什么

| 入口 | 典型问题 | 有对应数据时的交付 |
| --- | --- | --- |
| [事业](./onda-shiye/SKILL.md) | 这两个岗位怎么比较？ | 事业特点与约束、已知职责对照、需要核实的岗位条件 |
| [缘分](./onda-yuanfen/SKILL.md) | 我们相处时哪里合拍、哪里费力？ | 双人互补与磨合分别解释、一件可沟通的具体事情 |
| [时运](./onda-shiyun/SKILL.md) | 这一阶段和下一阶段有什么变化？ | 实际算出的周期、时间边界和差异；粒度不足处明确保留 |
| [健康文化](./onda-jiankang/SKILL.md) | 五行健康标签是什么意思？ | 传统对应释义、结果适用范围、独立的生活观察建议 |
| [命格](./onda-mingge/SKILL.md) | 学习或做事方式有什么可参考？ | 特点、适用条件与可自行核对的经验，不替代能力测评 |
| [星盘](./onda-xingpan/SKILL.md) | 我的盘里最值得理解什么？ | 关键星体／落点／相位及问题关联，盘式和精度说明 |
| [问事](./onda-zhanbu/SKILL.md) | 这件事我该留意什么？ | 起卦信息与卦变依据、传统含义、现实选项的核对条件 |
| [全面画像](./onda-zige/SKILL.md) | 三套体系分别怎么看我？ | 按主题对照来源、重合与分歧，显示缺失维度 |
| [风水](./onda-fengshui/SKILL.md) | 这些物件现在怎样，候选改法有什么不同？ | 逐对象事实与规则、条件判断、候选差异及未覆盖项 |

短问短答；需要比较或时间变化时再用小表。完整画像、逐物件审查和完整文件按用户请求展开。不会为展示更多工具强行增加体系、重复计算或补造经历。

---

## 发现与调用范围

个人命理工具按 8 个场景组织，独立风水咨询通过第 9 个 `onda-fengshui` 场景调用 `fengshui_*` 工具；住宅输入与分层合同见 [家居风水](../docs/fengshui.md)。当前 REST 公开 86 个工具，MCP 公开 87 个工具，各端绑定差异见 [API 参考](../docs/api-reference.md#24-三端能力边界)，完整工具地图见 [`_shared/fatebridge-engine.md`](./_shared/fatebridge-engine.md)。

机器场景清单另包含 `fengshui` 基础计算路由，共 10 项。`onda-fengshui` 是咨询技能入口，`fengshui` 是工具发现中的计算路由；两者均可用于场景筛选，具体内容以 `fatebridge scenarios --detail full` 为准。

---

## 目录结构

```
skills/
├── _shared/
│   ├── fatebridge-engine.md   计算层：CLI 调用、全量工具地图、字段字典、怎么读 snapshot
│   ├── onda-counsel.md        解读层：问题、依据、现实建议及 Onda 声音
│   └── consultation-delivery.md  按需读取的对照、时间线与解释示例
├── onda-yuanfen/              缘分 · 感情合婚
│   ├── SKILL.md               问题路由、计算依据与用户交付
│   └── agents/interface.yaml  给机器读：场景、工具清单、必填输入、输出契约
├── onda-shiye/                事业 · 财运
├── onda-jiankang/             健康 · 身心
├── onda-shiyun/               人生时运 · 择时
├── onda-zhanbu/               抉择 · 问事占卜
├── onda-mingge/               认识自己 · 性格天赋
├── onda-xingpan/              星盘 · 占星自观
├── onda-zige/                 全面自我画像 · 三套交叉印证
└── onda-fengshui/             风水 · 空间布局（另含 references/）
                               （每个 onda-* 都含 SKILL.md、agents/interface.yaml 与 agents/openai.yaml）
```

每个场景 Skill 有两份契约。`SKILL.md` 说明问题路由、证据读法和交付方式；`agents/interface.yaml` 给 agent 运行时读，声明场景触发词、引擎工具、输入和输出。计算和声音共用 `_shared/`，复杂场景的交付参考按需加载。

`tests/test_skills_interface_contract.py` 核对接口声明与引擎目录、SKILL.md 的一致性；`test_skills_engine_contract.py` 验证实际调用示例。静态合同与真实多轮对话质量分别验收。

九个场景都有 Codex 原生 `agents/openai.yaml`，允许自动选择，也可显式输入 `$onda-shiye`、`$onda-yuanfen` 等技能名。仓库 `.agents/skills/onda-*` 是指向本目录各技能的发现入口，维护源仍为 `skills/`；引用依赖随仓库保留，不只复制单个 SKILL.md。新 Codex 会话扫描项目技能，已有会话可能需要重新加载。MCP 可按 `FATEBRIDGE_MCP_SCENARIOS=onda-fengshui` 等场景名限制公开工具；这与技能发现是两个入口。

咨询按当前聊天已确认资料核对所选计算的缺项，普通首轮使用已验证字段、严格投影并关闭快照，通常先给要点、2–3 条依据及一项现实建议。完整 JSON 或文件请求首次保留 `fields=null` 与所需快照，按[同次导出](../docs/agent-guide.md#完整结果交付与同次导出)交付。详细分析与完整审查按请求展开，分数、传统规则和现实建议分别说明。

---

## 给开发者

新增或调整能力时，记住这条：**新维度请指向对应的 `bazi_*` 或工具目录条目，不要在 Skill 里手写排盘步骤。**

引擎侧加工具的方法看 [开发指南](../docs/development-guide.md#新增或修改一个领域能力)：领域声明位于 `src/fatebridge/services/catalog/`，`services/tool_catalog.py` 负责中央装配；声明对应 surface 后由注册器派生入口。嵌套 CLI 输入须显式启用 JSON 请求合同，不能假定每条目录记录三端均可执行。

任何在 Skill 里引用的 CLI 命令，提交前都要真跑一遍。先通过 `uv sync --locked --extra dev` 安装本仓库并激活 `.venv`（见 [开发指南](../docs/development-guide.md)）。运行 CLI 不用起 REST 服务；`python3` 必须指向已安装包的解释器：

```bash
python3 -m fatebridge.cli list
python3 -m fatebridge.cli describe <tool>
```

如果改了某个 skill 的工具或输入，记得同步更新它的 `agents/interface.yaml`，并按[文档维护流程](../docs/development-guide.md#文档维护与验证)重新生成场景 manifest。`engine_tools` 必须与 SKILL.md 里反引号引用的工具完全一致，否则 `tests/test_skills_interface_contract.py` 会失败。

---

## 许可与发布

本套件随 FateBridge Git 仓库以 **Apache License 2.0** 分发（见仓库根 `LICENSE`），当前 wheel 不包含 `skills/`；使用场景技能需取得对应仓库目录。每个 `agents/interface.yaml` 里标注的 `license` 和 `version` 都与项目一致，并由契约测试校验，保证对外分发时声明和实际不跑偏。

---

## 边界声明

所有解读都是传统术数与占星的文化参考视角，不是决定论，也不替代医疗、心理、法律、财务等专业意见。幸福靠真实地生活和经营，不靠命定。
