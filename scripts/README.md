# 维护脚本

通用开发入口留在本目录，领域审计、参考采集与研究工具按计算领域归档。确定性业务计算仍由 `src/fatebridge/` 提供，脚本不作为另一个生产实现。

从仓库根目录使用锁定环境：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python scripts/run_ci_checks.py
```

## 常用入口

| 任务 | 入口 |
| --- | --- |
| 文档链接、代码块和 JSON 语法 | [check_docs.py](check_docs.py) |
| 场景清单、按需调用合同 | [build_scenario_manifest.py](build_scenario_manifest.py) · [build_codex_call_contracts.py](build_codex_call_contracts.py)；生成后用 `--check` 核对 |
| 自包含 CI 集合 | [run_ci_checks.py](run_ci_checks.py)，分片插件为 [ci_sharding.py](ci_sharding.py) |
| Onda 插件打包 | [build_onda_plugin.py](build_onda_plugin.py) |
| 本地协议体验、真实模型评测 | [experience_codex.py](experience_codex.py) · [evaluate_agent.py](evaluate_agent.py) |
| 发布检查与 GitHub Release 同步 | [check_pypi_release.py](check_pypi_release.py) · [sync_github_release.py](sync_github_release.py) |
| 构建与缓存清理 | [clean_repository.py](clean_repository.py)，默认预览，`--apply` 执行 |

模型评测、外部资料下载及可选原生构建按各入口的帮助和[开发指南](../docs/development-guide.md)准备环境；普通 CI 不启动模型或下载独立参考。

## 领域目录

| 领域 | 目录 |
| --- | --- |
| 八字、旺衰与交运 | [bazi/](bazi/) |
| 星历、太阳交节、时标和物理参考 | [astronomy/](astronomy/) |
| 西占、德国盘、宫制与推运 | [western/](western/) |
| 占星骰的天文参考和误差分析 | [astrodice/](astrodice/) |
| 人类图、印度占星 | [human_design/](human_design/) · [jyotish/](jyotish/) |
| 果老、紫微、宿曜 | [guolao/](guolao/) · [ziwei/](ziwei/) · [sukuyo/](sukuyo/) |
| 梅花、六爻、河洛与参评 | [meihua/](meihua/) · [liuyao/](liuyao/) · [numerology/](numerology/) |
| 六壬与金口诀、奇门、太乙与三式 | [ren/](ren/) · [qimen/](qimen/) · [taiyi/](taiyi/) |
| 风水、地磁与玄空来源 | [fengshui/](fengshui/) |
| 外部评估、跨领域验收 | [evaluation/](evaluation/) · [validation/](validation/) |
| 地点与经文目录采集 | [catalogs/](catalogs/) |

例如：

```bash
uv run --locked --extra dev python scripts/bazi/audit_bazi_source_corpus.py --help
uv run --locked --extra dev python -m scripts.astronomy.audit_complete_moshier_accuracy --help
```

`audit_*` / `check_*` / `verify_*` 核对当前实现、来源或数学关系；`gen_*` / `build_*` / `fetch_*` / `collect_*` 获取或整理参考；文件名不是验收等级。先读模块说明和 `--help`，需要独立解释器、编译器或外部资料时按具体入口准备。审计非零退出可能表示保留的原典分歧或数值失败，不能为了让退出码变绿而重建答案、改分母或放宽门槛。

## 维护规则

新增脚本放入所属领域，先检查现有入口能否扩展；通用开发命令才留在顶层。领域之间用完整包路径导入，领域命令优先使用 `python -m scripts.<领域>.<模块>`；明确支持的直接文件入口另行验证。不要给移动后的脚本另留一份兼容包装。

独立参考生成器即使不被生产代码导入，也可能承担来源复现职责。退役前检查测试、CI、文档、其他脚本及原始来源记录；保存仍有价值的参考、失败与取得方法。原始资料在 `tests/data/`、`tests/fixtures/` 或外部固定档案中维护，不混入脚本目录。完整规则见[仓库维护](../docs/repository-maintenance.md)。

固定队列已有测试直接调用验证函数时，不再另维护只解析默认路径、打印 JSON 的脚本。梅花取数、历表、原典和天气规则统一运行 `uv run --locked --extra dev python -m pytest -q tests/meihua`；`scripts/meihua/` 保留参考采集、明确指纹的外部输入和原研究绑定检查。

果老卷45异本和人类图具名定爻例分别运行 `tests/guolao/test_guolao_witnesses.py` 与 `tests/human_design/test_human_design_primary_fixing_source.py`。测试直接执行来源审计，保留全部异文、未决项、冻结资料身份检查和错误注入；不另维护固定结果打印入口。

六爻的常规来源配置统一用 `uv run --locked --extra dev python -m scripts.liuyao.build_profile --check` 核对，也可在 `--check` 前指定 `role`、`strength` 等名称。各配置仍校验自己的冻结材料、原扫描和适用勘误；扫描校读、月破、刑及动巳的专门裁定继续由各自的构建器处理。果老原历不再为每个领域函数维护 JSON 打印命令；直接对照见 `tests/guolao/`，独立参考采集与完整来源审计仍在 `scripts/guolao/`。

八字未来时钟队列只保留 [一个执行器](bazi/audit_bazi_dayun_future_clocks_shard.py) 和 [一个合并器](bazi/merge_bazi_future_clock_shards.py)。执行器默认单片完整运行，需要分片时显式传入 `--shard-index` 与 `--shard-count`；合并仍检查完整原队列、顺序、未知状态与失败记录。

旧的单独 Li Chun、地磁、出版方本命及太乙交节 JSON 打印包装已移除；对应的完整来源与失败控制分别由 `tests/fengshui/test_fengshui_calendar_v10.py`、`tests/fengshui/test_fengshui_geomagnetic.py`、`tests/human_design/test_human_design_publisher.py` 和 `tests/taiyi/test_taiyi_solar_sources.py` 保留。人类图 Profile 验收统一使用 [完整原队列入口](human_design/audit_human_design_profile_full_coverage.py)，保留原 19／193 例、768 计划与缺项，不再维护只审查单个子队列的旧入口。AA1996 构建使用 `python -m fatebridge.fetch_aa1996`，见[太阳后端](../docs/solar-backends.md)。
