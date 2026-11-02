# 风水历法完整星历配置

[立春验收](fengshui-calendar.md) · [时间边界规范](../skills/onda-fengshui/references/calendar-boundaries.md) · [文件来源清单](../src/fatebridge/data/astro/ephemeris-manifest-v1.json)

当前源码与本地构建wheel提供 `fengshui_calendar` Swiss文件安装配置。它取得覆盖1784–2204年完整宅运边界的行星／月球文件：`sepl_12.se1`、`semo_12.se1`、`sepl_18.se1`、`semo_18.se1`。1800–2199是事件有效年的输入范围，不能因此漏掉前后完整二十年区间。

无外部严格JPL配置时，当前默认太阳交节使用打包DE440及[风水历史扩展](fengshui-historical-calendar.md)，本页四个Swiss文件不替换该默认模型。本页用于补齐原生Swiss路线的数据；验证该路线时显式选择`native`并核对实际返回模型，不以文件下载成功判断正在使用Swiss求交点。

源码环境运行：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile fengshui_calendar
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile fengshui_calendar --verify-only
uv run --locked --extra dev fatebridge doctor --family fengshui
```

安装了包含本功能的wheel时，在该环境使用 `python -m fatebridge.fetch_ephe --profile fengshui_calendar`。现有PyPI发布与本地修改分别验收，本页不表示新功能已经发布。

## 取得与发现

- 有既存项目 `ephe/*.se1` 时在该目录补齐四个文件；普通wheel安装没有该目录时写入用户缓存，不向只读安装目录写数据。
- 用户缓存优先采用绝对 `XDG_CACHE_HOME/fatebridge/ephe`；未指定时，macOS为 `~/Library/Caches/fatebridge/ephe`，Windows为用户LocalAppData下的 `fatebridge/ephe`，其他平台为 `~/.cache/fatebridge/ephe`。相对XDG路径不作为缓存根。
- 下载内容必须符合固定上游提交的字节数、SHA-256与Swiss文件头。已有正确文件不重下；替换旧文件沿用可恢复备份与原子写入。计算与doctor不会隐式下载。
- 新进程在显式 `SE_EPHE_PATH`、显式运行时路径及项目数据目录之后，才发现完整且匹配内置版本的用户缓存。部分、损坏或其他版本缓存不自动启用。运行中的进程需重启；不声称修改文件能热更新既有内存状态。

自选目录时：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe \
  --profile fengshui_calendar --dest /absolute/short/path/ephe
```

按输出提示在启动前设置 `SE_EPHE_PATH`。已有显式路径不会被缓存覆盖；若它选择其他目录，输出会明确要求更新路径，不误报缓存已启用。Swiss路径长度限制仍有效，不通过悄悄截断路径取得“可用”结果。只有已验证的完整缓存且未被更高优先级目录遮蔽时，才提示自动发现。数据单独取得，不随wheel分发；其来源与授权说明见[NOTICE](../NOTICE)和[上游资料](https://www.astro.com/swisseph/swephprg.htm)。

## 验收链

`doctor.fengshui_calendar` 返回当前搜索路径、逐目录及缓存文件身份、安装命令参数。`all_files_verified`只表示文件匹配所选版本，不能代替实际返回模型或天文精度核验；doctor顶层 `ok`也不是风水精度认证。

明确验证本页原生Swiss路线：

```bash
FATEBRIDGE_SOLAR_TERM_MODEL=native \
  uv run --locked --extra dev python scripts/audit_fengshui_calendar.py
```

同一套421项JPL参考、同一1秒TT实现门槛下，此前隔离wheel实际使用Moshier的无文件基线375项通过、46项失败；取得四个文件并由新进程自动发现后421项通过，最大差约0.106秒。没有改变原参考或放宽容差。安装配置不会让Moshier算法本身变得更准，原46项失败继续保留。

默认DE440的[全部24节气验收](fengshui-all-terms-calendar.md)与上述历史Swiss成绩分别记录。复建原Moshier控制时，显式设置 `FATEBRIDGE_SOLAR_TERM_MODEL=native` 并核对返回标志；不能仅凭星历目录为空判断模型，也不把该控制成绩套给其他数值模型。各模型边界原因及可读说明见[边界证据链](fengshui-model-boundary-fidelity.md)。

这只核对上述有限范围的TT太阳交点和部署数据链，不证明绝对UTC秒级精度、整部原典一致性或现实预测有效性。
