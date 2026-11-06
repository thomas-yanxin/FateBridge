# 星历数据安装与运行模型

[文档中心](README.md) · [快速入门](getting-started.md) · [太阳后端](solar-backends.md) · [分项精度验收](precision-acceptance.md)

准备数据前先完成[安装](getting-started.md#安装)。普通计算不会自动下载外部星历；以下操作需要网络，`--verify-only` 除外。下载、文件校验、实际运行模型与独立数值验收分别确认。

## 选择与准备数据

计算能运行，还需要知道它实际用了什么数据。`swisseph` 可导入，只能证明运行时可用。缺少相应 `.se1` 文件时，它可能使用内置 Moshier 模型；没有运行时的核心星盘则使用 FateBridge 轨道近似。显式复杂宫制与西占推运缺 backend 时会报错。

### Swiss 分段文件

源码安装可在仓库根目录下载默认星历段（此步骤需要网络）：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
```

默认下载 `sepl_18.se1`、`semo_18.se1`、`seas_18.se1` 到源码仓库 `ephe/`；所需年代/天体的数据可能不同。

### 按年份下载与离线校验

按所需公历年份选择行星和月球分段，可用 `--years 1500 9999`；连续范围用 `--year-range 2399 2401`。这些选项与 `--files` 互斥，并在600年分段交界包含相邻年份可能需要的文件，以覆盖民用时、TT/UT与历史历法换年边界。年份选择不下载主小行星文件，也不证明所有输入的星历精度；实际计算模型仍以回执为准。例如：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 9999
```

这会选择 `sepl_96.se1`、`semo_96.se1`，对应官方文件表的9600–10199年分段。直接提供文件名的旧入口继续可用。下载到自定义目录后，须设置运行服务的 `SE_EPHE_PATH`；下载成功本身不代表服务已读取该目录。

下载器按随包的 `ephemeris-manifest-v1.json` 固定官方提交，并核验文件长度及完整SHA-256；当前清单包含153份官方 `.se1` 文件的指纹，不包含数据文件本身。已有缓存也须校验；需要替换的旧内容先保存到目标目录的 `.fatebridge-ephemeris-backups/<旧SHA-256>/<文件名>`，下载或写入失败时保留原文件。并发修改会中止替换，不能把只有 `SW` 前缀或错放的分段误报为可用。

可离线检查已有文件：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe \
  --year-range 1 9999 --verify-only
```

`--base-url` 可选择镜像，但仍须匹配所选清单。不同版本或自定义文件可传 `--manifest /absolute/path/catalog.json`；清单使用 `schema_version=1`、`base_url` 以及 `files` 映射，每份文件须有 `bytes` 和64位小写 `sha256`。自定义指纹仅证明字节符合该清单。文件校验不认证天文误差，也不会持续监控服务运行期间的数据修改。

### 独立安装与自定义路径

使用已安装包的虚拟环境时，可显式指定可写目录：

```bash
python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe
export SE_EPHE_PATH=/absolute/path/to/ephe
```

通过 `uv tool install` 安装的用户可用独立运行环境下载到同一目录，无需寻找工具环境中的 Python：

```bash
uv run --no-project --with fatebridge python -m fatebridge.fetch_ephe \
  --dest /absolute/path/to/ephe
```

在各服务启动前设置 `SE_EPHE_PATH` 指向该目录；上面的 `export` 为 macOS / Linux 写法，Windows PowerShell 使用 `$env:SE_EPHE_PATH="C:\path\to\ephe"`。

非空 `SE_EPHE_PATH` 在 Swiss 底层优先于代码传入的显式路径，回执记录实际选择。当前接口的路径总长须在 242 个编码字节内，避免底层静默回退；可以使用更短的挂载路径。德国盘的 `seorbel.txt` 可能覆盖假设点轨道，即使物理星体仍使用 Moshier；查看 `midpoint_analysis.profile.hypothetical_element_source` 的来源说明。库的默认搜索路径还可能含当前工作目录。外部数据应在服务运行期间保持不变，更新后重启并复核实际模型及回执。

需要固定版本时，将 `--with fatebridge` 改为当前服务使用的 `fatebridge==<version>`。

重启服务后，检查核心盘的 `chart_profile.ephemeris_model`（如 `swieph`、`jpl`、`moshier`、`mixed`）和 `run_metadata.engine_is_approximate`，确认本次实际使用的模型。仅凭 `engine_backend` / `engine_precision` 不能证明加载了数据文件。数据路径、版本和算法限制见 [算法覆盖矩阵](algorithm-coverage.md)。

## 严格 JPL DE441

跨年代精度核对可显式安装完整原始 DE441（2,788,676,624 字节），再选择已有的严格 JPL 后端：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441
uv run --locked --extra dev python -m fatebridge.fetch_jpl --dest /absolute/path/to/jpl-de441 --verify-only
export SE_EPHE_PATH=/absolute/path/to/jpl-de441
export FATEBRIDGE_JPL_FILE=linux_m13000p17000.441
```

省略 `--dest` 时使用当前用户星历缓存下的 `jpl-de441/`，命令会打印实际目录。下载器从 JPL 官方地址流式下载，检查固定字节数、完整 SHA-256 和 DE441 文件头，校验后原子安装；已有不匹配文件会报错并保留。指纹来自本项目历史独立读取器核对记录，并非 NASA 发布的校验和。`--verify-only` 不联网；自定义 CA 可用 `--ca-file /absolute/path/to/ca.pem`，仍须通过 TLS 证书验证。下载不会自动切换后端，也不修改服务配置；在启动环境设置上述两个变量并重启客户端／服务后，检查实际模型及 `physical_ephemeris_source.files` 中的文件名、覆盖范围与 DE 版本。

DE441 的长时间覆盖不代表各年代精度一致；[JPL 原论文](https://ssd.jpl.nasa.gov/doc/de440_de441.html)明确说明 DE440 在当前世纪更准确。原始文件头采用 TDB，现有原生调用入口采用 TT；文件校验不认证时标换算、视位置模型或预测效力。固定样本的误差线和仍未通过的项目见[当前算法状态](algorithm-status.md)。

需要连续 DE441 系数子集时，按[精确月球来源](precision-acceptance.md#使用精确月球来源)准备；该路径与完整文件下载分别校验。太阳交节默认使用随包 DE440，模型选择、数据身份及年份边界见[太阳后端](solar-backends.md)。
