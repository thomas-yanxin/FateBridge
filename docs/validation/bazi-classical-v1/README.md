# 古典旺衰、成格与喜用独立裁定 v1

本批只研究八字。历史报告以此前链路验收工作树为对象；合并前又在 master `ac83e03` 上重新验证，见 [master-integration.json](master-integration.json)。原典预期未改。采用《秘本子平真诠》世界书局扫描本正文的月令格局口径，整理为 `ziping_zhenquan_month_command_text_v1`。这是有版本边界的原典个案裁定，不是“所有古典流派一致”的结论，也不是新上线的通用算法。

先读 [裁定与分歧报告](report.md)。固定的原典标注在 [profile](../../../tests/fixtures/bazi_classical_v1/profile.json)、[rules](../../../tests/fixtures/bazi_classical_v1/rules.json)、[cases](../../../tests/fixtures/bazi_classical_v1/cases.json)、[probes](../../../tests/fixtures/bazi_classical_v1/probes.json)、[disagreements](../../../tests/fixtures/bazi_classical_v1/disagreements.json)。预期字段由目读原书手工整理，未由生产代码生成；不是另一位专家盲审。

实际输出与比较在 [all.json](all.json)。`reference-freeze.json` 固定输入与标注哈希；`source-crosscheck-addendum.json` 保留首次比较之后的原书交叉核对，原预期未改。初次标注中的姓名校正、第一次适配器漏读已有取格层的记录均保留。

在源码目录复现：

```sh
uv sync --locked --extra dev
uv run python scripts/audit_bazi_classical.py --split development --output /tmp/bazi-classical-development.json
uv run python scripts/audit_bazi_classical.py --split reserved --output /tmp/bazi-classical-reserved.json
uv run python scripts/audit_bazi_classical.py --output /tmp/bazi-classical-all.json
uv run pytest -q tests/test_bazi_classical_audit.py
```

审计命令当前预期退出 **1**：表示古典算法验收未通过。它会写全量报告；不得为了得到退出 0 修改原典预期。`pytest` 通过表示冻结、范围和差异留存机制正常，不表示古典算法通过。报告中的 `unsupported` 是当前适配器核查过的能力缺口；未来新增裁定能力时应审查适配器，不能仅以新增字段名称自动宣告通过。

本批只新增独立标注、审计工具、测试和报告，生产计算、权重及默认流派未改。上游时间、天文和四柱换算不在这些原书命式的验证范围内；也未把古代官职记述作为现实效果的验收标签。

完整离线包另存于 `/Users/thomas/Desktop/FateBridge-validation/2026-10-19-bazi-classical-v1/`，包含原 PDF、目读页图、辅助转录原件、源码快照、锁文件、原始运行、哈希和运行命令。主要参考原件：

- [国家图书馆藏《秘本子平真诠》扫描 PDF](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)：裁定依据，PDF 页从 1 起计。
- [东里书斋《子平真诠》](https://www.donglishuzhai.net/chapter/3722.html)：导航与校异线索；与扫描同源，不计为第二独立裁判。

合并验证：`uv run pytest -q tests/test_bazi_classical_audit.py tests/test_strength_v2.py tests/test_useful_elements_resolution.py`，289 项通过。当前脚本在 master 上运行时同时记录 `strength.py` 和 `element_relations.py` 指纹；历史 JSON 保留当时脚本与源码指纹，不重新覆盖。合并复跑不是新的未见验收。
