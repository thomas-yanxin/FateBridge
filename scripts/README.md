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
| 连续星历系数的无损存储 | [astronomy/build_coefficient_archives.py](astronomy/build_coefficient_archives.py)，从五份原始DE440提取暂存件及连续DE441源构建两个运行时档案；`--check`核对分发数据，使用方法见[星历说明](../docs/ephemeris.md) |
| 按需调用合同 | [build_codex_call_contracts.py](build_codex_call_contracts.py)；生成后用 `--check` 核对 |
| 自包含 CI 集合 | [run_ci_checks.py](run_ci_checks.py)，分片插件为 [ci_sharding.py](ci_sharding.py) |
| 本地协议体验、真实模型评测 | [experience_codex.py](experience_codex.py) · [evaluate_agent.py](evaluate_agent.py) |
| 发布检查与 GitHub Release 同步 | [check_pypi_release.py](check_pypi_release.py) · [sync_github_release.py](sync_github_release.py) |
| 构建、缓存与原始扫描去重 | [clean_repository.py](clean_repository.py)，默认预览，`--apply` 执行；原始扫描另加 `--deduplicate-scans` |

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
uv run --locked --extra dev python -m scripts.astronomy.audit_solar_model_reference --help
```

`audit_*` / `check_*` / `verify_*` 核对当前实现、来源或数学关系；`gen_*` / `build_*` / `fetch_*` / `collect_*` 获取或整理参考；文件名不是验收等级。先读模块说明和 `--help`，需要独立解释器、编译器或外部资料时按具体入口准备。审计非零退出可能表示保留的原典分歧或数值失败，不能为了让退出码变绿而重建答案、改分母或放宽门槛。

## 维护规则

新增脚本放入所属领域，先检查现有入口能否扩展；通用开发命令才留在顶层。领域之间用完整包路径导入，领域命令优先使用 `python -m scripts.<领域>.<模块>`；明确支持的直接文件入口另行验证。不要给移动后的脚本另留一份兼容包装。

独立参考生成器即使不被生产代码导入，也可能承担来源复现职责。退役前检查测试、CI、文档、其他脚本及原始来源记录；保存仍有价值的参考、失败与取得方法。原始资料在 `tests/data/`、`tests/fixtures/` 或外部固定档案中维护，不混入脚本目录。完整规则见[仓库维护](../docs/development-guide.md#仓库维护)。

太阳TT固定参考使用 [astronomy/build_solar_term_reference.py](astronomy/build_solar_term_reference.py) 生成自带生成源码的独立资料包，读取与固定身份校验由 [astronomy/solar_term_reference.py](astronomy/solar_term_reference.py) 维护。复现环境、内核和范围见[资料说明](../tests/data/solar_tt_de440_v1/README.md)；日常回归使用 `tests/astronomy/test_solar_term_reference.py`。接受外部矩阵的TT诊断保留模块入口 `uv run --locked --extra dev python -m scripts.ren.audit_ren_model_tt --help`，分别报告现行参考来源、旧侧件缺口和原刊载分钟失败。

六壬完整秒级与分钟条件参考共用 [ren/ren_boundary_reference.py](ren/ren_boundary_reference.py)，不在两个审计器分别追旧路径与报告哈希。当前独立生成器为 [ren/build_ren_boundary_reference.py](ren/build_ren_boundary_reference.py)，输入与复现方式见[边界资料](../tests/data/ren_boundary_sources_v1/README.md)。接受外部星历配置及输出位置的完整审计可用 `python -m scripts.ren.audit_ren_seconds --help` 和 `python -m scripts.ren.audit_ren_boundary_decisions --help`；旧来源身份、区间不确定和分钟差异分别报告，不把完成新来源链写成恢复旧侧件。

固定队列已有测试直接执行完整验证时，以对应领域测试为入口，不另维护一份默认路径、参数别名和 JSON 打印包装。果老原历、圭表、黄赤道、漏刻与限度核对统一运行 `uv run --locked --extra dev python -m pytest -q tests/guolao`；该目录继续保留原典字面、完整参考队列、刊差及输入拒绝验证。果老脚本只保留资料采集、外部数值审计、回放资料验证及预测研究等独立任务。

六壬／金口诀与太乙的固定来源审计由 `tests/ren/`、`tests/taiyi/` 直接调用完整审计函数；这些模块不另提供参数解析和 JSON 输出入口。原典分歧及未决项仍由结果和断言保留，pytest 通过不表示原典符合性通过。太乙 `audit_taiyi_wujing_internal.py` 保留仅标准库的独立进程复核；接受外部输入的研究工具、资料采集器与数值参考生成器继续保留命令入口。

八字原典位置核对运行 `tests/bazi/test_classical_routes.py`；金口诀早稻田课目与旺衰分别运行 `tests/ren/test_jinkou_waseda_chapter.py`、`tests/ren/test_jinkou_waseda_strength.py`；三式贵人两版本完整表运行 `tests/taiyi/test_sanshi_noble_sources.py`。风水原文、完整下卦／替卦图、日时表与历法选择按 `tests/fengshui/` 的对应来源测试核对，各自保留分歧，不另设跨来源总分或总审计包装。

WMM2025精确WGS84参考由[独立多项式生成器](fengshui/build_fengshui_wmm_wgs84_reference.py)维护：明确传入原始NOAA `--coefficient-file`、冻结输入`--cases-file`和`--output`，可用`--full-output`另存80／120位完整结果。常规测试读取[可移植参考](../tests/fixtures/fengshui-wmm-wgs84-reference-v1.json)，不在CI中重新生成期望值。原100点表及未修改官方C的独立门槛继续保留，见[验收口径](../docs/precision-acceptance.md#wmm2025的精确wgs84主场求值)。

原生坐标框架的[单位轴参考生成器](astronomy/build_native_frame_reference.py)接受原作者固定提交的`--source-directory`、含`epochs`与`frames`的`--cases-file`、明确的`--compiler`及`--output`；Clang/macOS构建另给`--sysroot`。它核对源文件后重新编译原C，直接变换单位轴。常规测试读取[全部734组固定参考](../tests/fixtures/native-source-frame-reference-v1.json)，不调用生产计算器生成期望值。数值范围和原始误差增减见[框架验收](../docs/precision-acceptance.md#原生框架反求病态修复)。

需要专门运行方式的入口：

| 任务 | 入口与要求 |
| --- | --- |
| 梅花取数、历表、原典和天气规则 | `uv run --locked --extra dev python -m pytest -q tests/meihua`；研究绑定统一用 `python -m scripts.meihua.audit_meihua_weather_study --check trace`；检查项可选 `trace`、`calendar`、`solar` 或 `context-capacity`，原始资料与报告路径另行指定；参考采集保留独立入口 |
| 六爻来源配置 | `python -m scripts.liuyao.build_profile --check`；可在 `--check` 前选 `role`、`strength` 等配置，专门扫描／勘误仍由对应构建器处理 |
| 人类图 Profile | [完整队列审计](human_design/audit_human_design_profile_full_coverage.py)，保留19／193例、768计划及缺项 |
| 参评 DE440 投影资料 | `python -m scripts.numerology.build_canping_projection_profile --kernel <de440.bsp> --profile original --check`；第二份固定队列用 `--profile extended`，两份协议与原始字节分别验证 |
| AA1996来源构建 | `python -m fatebridge.fetch_aa1996`，见[太阳后端](../docs/solar-backends.md) |

参评 `extended` 现有本地协议与已发数据清单的 `selection_protocol_sha256` 不一致，`--check` 保留该失败；不得自动改写既定来源指纹。两组提取的原始系数仍分别按其固定范围核对。

表中 Python 命令均在仓库根目录使用 `uv run --locked --extra dev` 前缀。
