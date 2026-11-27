# 星历数据安装与运行模型

[文档中心](README.md) · [快速入门](getting-started.md) · [运行配置](configuration.md) · [故障排除](troubleshooting.md)

准备外部星历前请先完成[安装](getting-started.md#安装)。常规安装与普通计算不会自动下载外部星历；除 `--verify-only` 外，以下获取命令均需要网络连接。

## 模型选择与降级边界

`swisseph` Python 库可导入只说明原生库存在，不代表外部 `.se1` 数据文件已配置。缺少 `.se1` 时，核心星盘会回退至内置 Moshier 模型或离线近似轨道，而显式非整宫宫制与西占推运（`astro/timing*`、事件与生命周期技法）缺乏可用运行时时会直接返回 `dependency_missing`。

每次星历相关调用后，应同时核对返回中的 `chart_profile.ephemeris_model`（`swieph`、`jpl`、`moshier`、`mixed`）与 `run_metadata.engine_is_approximate`；安装或切换目录后须重启对应进程（REST / MCP）。

## 安装 Swiss `.se1` 分段文件

### 源码与年份范围下载

源码检出可在仓库根目录下载默认星历段（`sepl_18.se1`、`semo_18.se1`、`seas_18.se1` 到 `ephe/`），或按公历年份与连续区间获取相邻 600 年分段交界文件：

```bash
uv run --extra dev python -m fatebridge.fetch_ephe
uv run --extra dev python -m fatebridge.fetch_ephe --years 9999
uv run --extra dev python -m fatebridge.fetch_ephe --year-range 1 9999 --verify-only
```

`--years` 与 `--year-range` 与 `--files` 互斥；`--verify-only` 可离线校验本地已有文件，还可通过 `--base-url` 指定镜像或 `--manifest` 指定自定义清单。

### 独立安装与 `SE_EPHE_PATH` 限制

独立工具或自定义目录安装时，用 `--dest` 指定可写目录并导出 `SE_EPHE_PATH`：

```bash
uv run --no-project --with fatebridge python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe
export SE_EPHE_PATH=/absolute/path/to/ephe
```

Windows PowerShell 使用 `$env:SE_EPHE_PATH="C:\path\to\ephe"`。非空 `SE_EPHE_PATH` 在 Swiss 底层优先于代码传入的默认路径；多目录在 Unix 下用 `:` 或 `;` 分隔，Windows 保留盘符冒号。**整条 `SE_EPHE_PATH` 字符串须控制在 242 个编码字节以内（单个文件拼接路径须小于 256 字节）**，超长会导致底层静默回退。

## 严格 JPL DE441

跨年代高精度核对可安装完整原始 DE441 二进制内核，并同时配置目录与短文件名：

```bash
uv run --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441
uv run --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441 --verify-only
export SE_EPHE_PATH=/absolute/path/to/jpl-de441
export FATEBRIDGE_JPL_FILE=linux_m13000p17000.441
```

省略 `--dest` 时默认写入用户缓存目录下的 `jpl-de441/`；因 Swiss 2.10.03 限制完整文件路径不超过 255 字节，建议将下载目录控制在 232 字节以内。企业代理或自签名证书环境可传 `--ca-file /absolute/path/to/ca.pem`。配置后重启服务，可在结果中核对实际模型与 `physical_ephemeris_source.files`。

## DE441 系数分片与太阳交节模型

### `FATEBRIDGE_DE441_DIR` 系数分片

Python 分发包（wheel / sdist）默认不包含约 600 MiB 的 `de441-planetary-*-part-*.bin.gz` 连续行星系数分片；源码检出直接读取 `src/fatebridge/data/astronomy/`。使用 wheel 或 sdist 且需要离线连续冥王星／DE441 系数时，需从对应版本源码归档提取分片并将 `FATEBRIDGE_DE441_DIR` 设为该目录的绝对路径；缺少所需分片时引擎返回不可自动重试的 `de441_archive_missing`。

### `FATEBRIDGE_SOLAR_TERM_MODEL` 太阳交节模型

太阳交节在 `FATEBRIDGE_SOLAR_TERM_MODEL=auto` 下，1700–2300 年默认采用随包分发的 DE440 共享太阳系数（若设置了 `FATEBRIDGE_JPL_FILE` 则优先走严格 DE441）。可选显式模式及对应环境变量如下：

| 模式取值 | 说明与环境变量 |
| --- | --- |
| `auto`（默认） | 1700–2300 年优先使用随包 DE440；若启用 `FATEBRIDGE_JPL_FILE` 则用严格 DE441 |
| `de440` / `native` / `swiss` / `analytic` | 分别显式锁定随包 DE440（1700–2300 年）、原生路径、Swiss 物理文件或 ERFA 解析对照 |
| `spk` | 需配合 `FATEBRIDGE_SOLAR_SPK_FILE` 指定外部 SPK 内核并安装 `jpl` 可选依赖 |
| `vsop2013` | 需先运行 `fatebridge.fetch_vsop2013 --output <dir>` 构建并设置 `FATEBRIDGE_VSOP2013_MANIFEST`（1700–2300 年） |
| `aa1996` | 需先运行 `fatebridge.fetch_aa1996 --output <dir>` 构建并设置 `FATEBRIDGE_AA1996_MANIFEST` |

严禁将显式 `analytic`、`spk`、`de440`、`aa1996`、`vsop2013` 与严格 `FATEBRIDGE_JPL_FILE` 混用，或在计算过程中替换外部文件，否则引擎返回 `ephemeris_source_inconsistent`（503，`retryable=false`）。如需校验或重建随包系数档案，运行 `uv run --extra dev python scripts/astronomy/build_coefficient_archives.py --check`；外部数据与三方许可见 [NOTICE](../NOTICE)。
