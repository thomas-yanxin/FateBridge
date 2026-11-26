# 星历数据安装与运行模型

[文档中心](README.md) · [快速入门](getting-started.md) · [运行配置](configuration.md)

准备数据前先完成[安装](getting-started.md#安装)。普通计算不会自动下载外部星历；以下操作需要网络（`--verify-only` 除外）。

## 选择与准备数据

`swisseph` 可导入仅表明运行时可用；缺少 `.se1` 数据文件时，核心星盘可能使用内置 Moshier 模型或离线近似轨道，显式复杂宫制与西占推运缺运行时则会报错。

### Swiss 分段文件

源码安装可在仓库根目录下载默认星历段（此步骤需要网络）：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
```

默认下载 `sepl_18.se1`、`semo_18.se1`、`seas_18.se1` 到源码仓库 `ephe/`。

### 按年份下载与离线校验

按所需公历年份选择行星和月球分段，可用 `--years 1500 9999`；连续范围用 `--year-range 2399 2401`。这些选项与 `--files` 互斥，并在 600 年分段交界包含相邻年份可能需要的文件。例如：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 9999
```

下载到自定义目录后，须设置运行服务的 `SE_EPHE_PATH`；下载成功本身不代表服务已读取该目录。可用 `--verify-only` 离线检查已有文件，`--base-url` 指定镜像，`--manifest` 指定自定义文件清单：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --year-range 1 9999 --verify-only
```

### 独立安装与自定义路径

使用已安装包的虚拟环境或独立工具环境时，可显式指定可写目录并配置 `SE_EPHE_PATH`：

```bash
python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe
export SE_EPHE_PATH=/absolute/path/to/ephe
```

通过 `uv tool install` 安装的用户可执行 `uv run --no-project --with fatebridge python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe`。Windows PowerShell 使用 `$env:SE_EPHE_PATH="C:\path\to\ephe"`。

非空 `SE_EPHE_PATH` 在 Swiss 底层优先于代码传入的显式路径。整条 `SE_EPHE_PATH` 列表须在 242 个编码字节以内（单个文件拼接路径须小于 256 字节），否则底层可能静默回退；Unix 使用 `:` 或 `;` 分隔多目录，Windows 保留盘符冒号。更新目录后请重启进程，并检查返回结果的 `chart_profile.ephemeris_model`（`swieph`、`jpl`、`moshier`、`mixed`）与 `run_metadata.engine_is_approximate`。

## 严格 JPL DE441

跨年代精度核对可显式安装完整原始 DE441 文件，并设置环境变量：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441
uv run --locked --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441 --verify-only
export SE_EPHE_PATH=/absolute/path/to/jpl-de441
export FATEBRIDGE_JPL_FILE=linux_m13000p17000.441
```

省略 `--dest` 时默认写入当前用户星历缓存下的 `jpl-de441/`。由于 Swiss 2.10.03 限制完整文件路径不超过 255 字节，下载目录建议控制在 232 字节以内。自定义 CA 可传 `--ca-file /absolute/path/to/ca.pem`。设置上述环境变量并重启服务后，可查看结果中的实际模型与 `physical_ephemeris_source.files`。

## DE441 系数分片与共享太阳系数

Python 分发包（wheel / sdist）默认不内置约 600 MiB 的 DE441 连续行星系数分片；源码检出可直接读取 `src/fatebridge/data/astronomy/`。使用 wheel 或 sdist 安装且需要离线连续冥王星／DE441 系数时，从对应版本的源码归档提取 `de441-planetary-*-part-*.bin.gz`，并将 `FATEBRIDGE_DE441_DIR` 设为该目录的绝对路径后启动服务；缺少所需分片时引擎返回 `de441_archive_missing`。

太阳交节在 1700–2300 年默认使用随包发布的 DE440 共享系数。若需重建或校验系数档案，请使用 [astronomy/build_coefficient_archives.py](../scripts/astronomy/build_coefficient_archives.py) 并加 `--check` 参数；外部数据与三方许可条件见 [NOTICE](../NOTICE)。
