# 六爻独立装卦参考

`reference.json.gz` 是实际运行原版 [ichingpy](https://github.com/JinyangWang27/ichingpy/tree/4eb8c0f7ba49fcd14d062be04a1bec8ba7554139) 0.1.11 的输出，先生成并冻结，再与 FateBridge 比较。原项目作者为 Jinyang Wang，代码采用 MIT 许可。这里保存的是程序输出；没有把第三方实现复制进领域引擎，也没有增加运行依赖。

队列含全部 4⁶ 种三钱六掷之和，等价于全部 64 × 64 本卦／变卦组合；另含 64 卦 × 10 日干的六神排列。爻序由初爻向上，第三方状态值为钱数减六。比较本变卦码、动爻、八宫五行、世应、纳支、支五行、本宫六亲及实际变爻六亲；第三方额外返回的纳干保存在原输出，但 FateBridge 尚未返回该字段，不计作通过。第三方按数次变爻查世应，FateBridge 使用宫序掩码表，属于不同实现路径。

冻结的完整 JSON SHA-256：`f39ef6082c334a5a93ec1dcbe8aafb22eeba7f20b08ba81257041490f664b7e5`。压缩字节、第三方全部源码文件、Python 及实际依赖版本见 `source.json`。校历、取用、旺衰、生克条件、应期和现实预测不在本参考验收范围；所用日干是共同输入。

`scan-tables.json` 另存同版影印第24–34页的具名八宫序、世应位置和八纯卦纳支栏人工读取。混卦纳支由相应经卦的内外三支拼接；没有声称逐字转录了384个混卦爻支。卦码由图形对应的上下经卦生成，避开原有维基表测试通过本项目《周易》资料生成器取得卦码的相关性。这里只核对选定表格；旧转录中的“辰在内”字节保留，艮卦按第28页图形及支栏另核，不覆盖原始资料。

离线测试直接读取本目录，不安装第三方。复现参考须在仓库外创建独立环境；下面的 `REFERENCE_DIR`、`REFERENCE_ENV`、`REFERENCE_OUTPUT` 应为工作目录外的实际路径。固定提交的源码、许可证和构建声明均保留在独立 checkout：

```bash
git clone https://github.com/JinyangWang27/ichingpy.git "$REFERENCE_DIR"
git -C "$REFERENCE_DIR" checkout 4eb8c0f7ba49fcd14d062be04a1bec8ba7554139
uv venv --python 3.12 "$REFERENCE_ENV"
uv pip install --python "$REFERENCE_ENV/bin/python" "$REFERENCE_DIR" 'pydantic==2.14.3'
"$REFERENCE_ENV/bin/python" scripts/liuyao/export_independent_chart_reference.py \
  --reference-repo "$REFERENCE_DIR" --output "$REFERENCE_OUTPUT"
```

导出器核对提交、源码工作树和实际导入包字节；输出应与本目录的 `reference.json.gz` 完全相同。环境回执可能随解释器或安装位置改变，不能据此改动原期望值。现有原典转录测试和所有结构断言继续保留。
