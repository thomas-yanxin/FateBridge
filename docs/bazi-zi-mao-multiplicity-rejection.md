# 二卯一子与一合一刑：完整条件实验及拒绝决定

[文档中心](README.md) · [前轮身印来源](bazi-energy-provenance.md) · 冻结方案（本地数据：`../tests/fixtures/bazi_zi_mao_multiplicity_v1/protocol-first.json`）

本轮未修改生产旺衰，默认仍为v10。一个依据原文区分二卯一子、合去一卯后恢复一刑的候选，在完整范围中修正C09控制，却使原有C10控制退化。候选因此拒绝采用；没有按有利子集重判门槛，原十九例仍有十七例分歧。

## 原页与阴阳约束

再读《秘本子平真诠》论刑冲会合解法PDF23（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/ziping-p23-first.png`）、PDF24（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/ziping-p24-first.png`）、PDF25（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/ziping-p25-first.png`），并保留PDF26章界（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/ziping-p26-first.png`）。所用国图藏世界图书馆本完整PDF散列沿用旧冻结记录；同一开发者目读，不是第二位专家认证。[东里数字原文](https://www.donglishuzhai.net/chapter/3720.html)只辅助核字，不冒充另一份已核原刊或独立学术审阅。

PDF24–25依次讨论甲生子月、两卯不刑一子，以及遇戌合去一卯后恢复一刑。甲日必须配阳支，固定月支子后，两处卯只能落在年、时，所以不能把这里的“相并”直接编码为邻接两卯。这是四柱阴阳约束所排除的实现，并不单独解决全部“相并”、争合或远近含义。

仅考虑这段条件与现代五虎遁、五鼠遁内部相容的字面四柱，二卯一子的甲日形式有25组：卯年五种天干，各对应子月干，甲日支在寅、辰、午、申、戌中选择，卯时为丁卯。戌日5组可有日时卯戌邻合，其余20组是C09机制诊断。它们是源条件的工程枚举，没有核实绝对出生日期，也不是25个新人物或事前预测样本。

## 事前冻结的候选

只处理恰有二卯、一子的实体刑组，不向一卯二子或其他刑组作对称推广。读取同次已成立的六合、三合、三会，移除其覆盖的参与者；半合趋势、争议候选及零效果附属关系不移除参与者。余下二卯一子时抑制刑损；一方已无参与者时按实际会合解除；合去一卯后余下一子一卯时，只对余下两原位置保留活动刑。

候选不查询命例ID、来源强弱、天干或相邻特例，也没有在看到结果后加“见戌便恢复刑”的分支。新判定只在隔离模块中运行，生产源码不改。实验回执中的v10字段保留副本所用的基础算术标识，配套experimental_provenance明确这不是公开v10结果或新的发布版本。

## 完整比较及失败

完整结果（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/audit-first.json`）核对20,736种支位排列，其中120种关系回执改变；所有改变再各查十种日干，共1,200份回执。长冻结的独立分数参考逐项核对，最大误差3.553e-15，仍用1e-12门槛。它条件化于给定离散关系，不独立认证原典语义或关系判定。

408条研究记录、367条公开输入、127条已知标签、281条未知及三项公开禁止档位约束均保留。实验只改变YL-03、DTCW1947-YX-01、DTCW1947-SJ09的数值；全部408条等级不变，YX-01原有弱与来源强的分歧仍存在。原19例完整assessment甚至在候选中也未改变，仍17例分歧，无新增原典准确率信用。

原章14项条件、9项控制全部保留：

| 冻结控制ID | 原先符合 | 候选符合 |
| --- | --- | --- |
| unique_zi_chou | 是 | 是 |
| unique_mao_xu | 是 | 是 |
| unique_water_formation | 是 | 是 |
| unique_wood_formation_relation_diagram | 是 | 是 |
| nonadjacent_pair_gap | 是 | 是 |
| nonadjacent_mao_xu_gap | 否 | 否 |
| two_mao_one_zi_gap | 否 | 是 |
| two_mao_after_binding_gap | 是 | 否 |
| clash_relieves_punishment_gap | 否 | 否 |

两边虽都是6/9符合，失败身份发生了变化：C09改善，同时C10退化。不能用相同通过数隐藏新增退化，也不能用已知标签未退化替代来源条件门槛。

C10旧控制为甲戌、丙子、甲卯、丁卯，早已标明日柱阴阳不相容，保留为关系图。戌与两个卯都不邻接，当前默认没有生成实际六合；旧结果的“活动刑”只是状态碰巧符合，不能证明“一合一刑”的机制已算对。候选忠于当前会合回执便找不到合去的卯，反而抑制刑，故这一门槛失败。没有删除这个旧关系图或修改其期望。

25组后续诊断（本地数据：`validation/bazi-zi-mao-multiplicity-files-v1/all25-source-parity-diagnostics-first.json.gz`）对前述甲日合法形式均符合所测C09/C10机制，但它们是在失败之后另立的机制诊断，不能顶替原控制、增加独立准确率信用或救回候选。

生产的四项新增来源条件检查首跑3失败1通过；冻结候选连同全部9项旧控制的显式门槛为10通过3失败，三项失败中有两项继承旧未解条件，一项是C10新增退化。全部首次XML、日志、输入、候选与独立参考保留；拒绝决定（本地数据：`../tests/fixtures/bazi_zi_mao_multiplicity_v1/rejected-candidate-decision-first.json`）没有重判。

## 下一项依赖与验收边界

问题要求联合处理非邻接六合、一个实体能否同时参与两合，以及合去者和仍参与刑者的具体位置。不能仅凭“见戌”指定任意一个卯，再为该位置扣根；原文条件、支位竞争和实际预算必须相容。当前分歧、月令司令与通关效力未裁定状态不变；“不扣一项刑损”也不足以认证身印轻重或有效通关。

本轮是未采用的计算研究，没有新的三端、wheel、部署或完整原典通过声明。核对1968条旧“合解冲”事件未发现缺少实际会合覆盖的内部矛盾，这份完整阴性探针也保留，不记作发现计算错误。新19题模型解释验收仍待原授权回复，本轮没有新模型调用；现实预测继续not_tested，整体目标及权威认证未完成。

~~~bash
# 原门槛保持失败，预期退出1
uv run --locked --extra dev python tests/fixtures/bazi_zi_mao_multiplicity_v1/run_candidate_gate.py --output /tmp/bazi-zi-mao-candidate-gate-replay.xml

# 核验完整证据和拒绝决定，不代表候选通过
uv run --locked --extra dev python scripts/audit_bazi_zi_mao_multiplicity.py --output /tmp/bazi-zi-mao-multiplicity-check.json
uv run --locked --extra dev pytest -q tests/test_bazi_zi_mao_multiplicity_research.py
~~~

首版运行器原文件保留；后续仅增加必填输出位置与防覆盖检查，断言及首次XML不改。重放需要v75冻结后端，并按原源码清单（本地数据：`../tests/fixtures/bazi_energy_provenance_v1/source-manifest-final.json`）逐文件核验。原临时目录与源码包已清理，当前无法直接重建这次历史运行环境；保留的首次结果不代表已完成新的重放。门槛运行器拒绝覆盖已有XML，原失败保留。不得以研究证据审计通过代替候选采用门槛。
