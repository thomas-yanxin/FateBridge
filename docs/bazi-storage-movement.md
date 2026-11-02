# 四墓土冲动与剩余根力

本轮修正直接影响旺衰计算的一条机制，并让摘要引用同次实际回执。历法、所选原典和解释忠实继续分别验收；不把局部规则符合率换算成整体满分。

## 原文与偏差

依据[国家图书馆藏《秘本子平真诠》书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)〈论墓库刑冲之说〉PDF44–45、印刷35–36页。已目读原页，原PDF的SHA-256为`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`。

原文区分四墓土的冲动与一般冲克。土为财官时，不因同类冲动直接伤土；水为财官时，土动可反累水。它不支持所有元素逢冲便被释放，也没有给出普遍数值系数或成格保证。

旧模型在辰戌、丑未冲时将整支藏干统一乘0.75，土根也一起减损；丑未戌齐全三刑又统一施加0.9减损。这把不同机制混成按支扣分，影响剩余根量、扶身份额、敏感性和下游喜用。

## v3计算规则

`season_root_revelation_relations_v3`加入`ziping_storage_movement_v1`，原`StrengthPolicy`参数及判级阈值不变。

| 条件 | 本事件处理 |
| --- | --- |
| 实际辰戌／丑未冲未被既有会合规则解除 | 对参与支逐个真实藏干记录系数，土根不作普通冲克减损 |
| 丑未戌齐全三刑 | 同样保留本事件土根；不把两支片段补为完整三刑 |
| 参与支水根 | 方向取土动克水；幅度仍为工程保留参数，冲0.75、刑0.9，非原典定量值 |
| 金木火等其他藏干 | 不因本条自动释放、增量或统一扣减 |
| 其他合绊、自刑等 | 继续分别作用，本事件保留土根不代表对其他关系免疫 |
| 重复作用 | 相关减损取最强，不重复相乘，不增造根气预算 |

寒湿燥土、完整生克流通及所有合冲先后异说仍未裁定。水受制程度有待验证；不能将这条有限形式化当作整体原典旺衰。

五个原文局部探针（本地数据：`../tests/fixtures/bazi_storage_movement_v1/reference.json`）在实现前手工冻结散列，包含甲用戊财、壬用己官、己用壬财、丁用壬官及癸用戊官。原文未给完整四柱，不补时辰。这些开发探针不替换旧原典验收的样本或分母。

## 同次回执与解释

标准命盘在`bazi_birth.day_master.assessment.relations`返回逐项事件；综合去掉`bazi_birth.`前缀。九专题及综合共享`evidence_chain.strength_context.storage_movement_effects`，复制已供给的实际旺衰关系，不再次推算。

| 字段 | 含义 |
| --- | --- |
| `event_retention_multiplier` | 本事件对该藏干的保留系数 |
| `combined_loss_multiplier` | 与其他已处理减损合并后的损耗系数，不能反向抹去本事件减损 |
| `remaining_hidden_mass` | 全部已有关系处理后的实际剩余藏干根量；模型内部单位，不作概率 |
| `earth_energy_bonus=0` | 本条不增造土能量 |
| `numeric_magnitude_origin` | 明示幅度为工程政策 |
| `formation_status=not_adjudicated` | 未以此判开库或成格 |

未提供旺衰关系计算时字段为`null`；计算后确无此类事件才为`[]`。标准命盘摘要只读取当次事件和系数；土根本事件系数为1，若另受合绊，最终系数仍可为0.85。输出模型拒绝虚构土能量、成格状态、字符串数值及同一事件内矛盾系数。任意自由文本推论仍需单独验收。

公历虚构回归为2024-10-22 00:00、Asia/Shanghai、直接钟时、男，实际四柱甲辰／甲戌／己未／甲子。三端返回同一条年辰与月戌事件，并核验同run引用；它不是真人或古代原典完整命例。

## 验收范围

原有21例方向对照仍21/21，15项参数逐一±15%共630次扰动未改标签。双人评分继续核对原先独立手工分项账，不改权重或数字参考，只更新运行模型标识。

冻结《子平真诠》命例取格仍10/10，旺衰仍1/3，另7例未裁定；成格、相神与完整救应仍未通过。该审计继续退出1。本轮没有借新增局部探针抹掉既有失败。

旧根容量实验的默认严格入口继续拒绝生产源码漂移；没有修改其候选、标注、依赖清单或第一次结果。新增`--historical-replay`可显式选择散列完全匹配原依赖的历史v2源码（本地数据：`validation/bazi-root-force-strength-baseline-v2.py.txt`），在私有导入空间重放原候选，不替换生产模块。当前环境或源码差异继续记录，采用条件保持未通过，历史结果不冒充当前v3表现。

```bash
uv run --locked --extra dev pytest -q \
  tests/test_storage_movement.py tests/test_storage_movement_transports.py \
  tests/test_strength_v2.py tests/test_compatibility_score_provenance.py
uv run --locked --extra dev python scripts/validate_bazi_strength.py
uv run --locked --extra dev python scripts/audit_bazi_classical.py \
  --output /tmp/fatebridge-classical-storage.json
uv run --locked --extra dev python scripts/audit_bazi_root_force.py \
  --historical-replay --allow-environment-drift \
  --output /tmp/fatebridge-root-force-historical.json
```

源码快照、三个维度的未完成项、逐项回归与资源补验、历史重放及打包证据见本轮验证记录（本地数据：`validation/bazi-storage-movement-v1.json`）。领域回归1,812项通过，唯一跳过项随后用实际星历文件补验通过；该结果不替代全仓或完整原典验收。
