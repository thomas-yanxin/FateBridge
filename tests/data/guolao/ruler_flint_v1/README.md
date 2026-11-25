# 果老原尺的独立有理数参考

本资料只验证明确的 12×30 名义历和给定录文的精确计算。七行尺格共
21,787 个整数名义日样本，另加 848 个有理子日，合计 22,635 个样本；
还保留全部 210 格的原印、公式端点及其差异。子日包括每个公式及原印
端点两侧的极小精确分数，以及每格内的 1/3、2/7 日。两项超小／超大
日期控制另计，不作为宫限内样本。

参考由 [python-flint 0.9.0](https://python-flint.readthedocs.io/en/latest/fmpq.html)
和 [FLINT 3.6.0 的有理数运算](https://flintlib.org/doc/fmpq.html)生成，
进程不导入 FateBridge，不用生产 `Fraction` 计算预期结果。FLINT 在对
有理数样本做集合去重时会导入标准库 `fractions`；这是依赖的哈希行为，
不应写成“进程未导入 fractions”。原始过严断言的失败和导入诊断保留在
仓库外阶段记录中。这里只接受逐项精确相等，不使用浮点误差阈值。

原文来自国图藏、蔣廷錫及陳夢雷等辑、清雍正四年（1726）内府铜活字本
[《钦定古今图书集成》第3150册](https://commons.wikimedia.org/wiki/File:NLC892-411999021002-92845_欽定古今圖書集成_第3150冊.pdf)
第35页七条率文及第36页全部210格。PDF为24,732,787字节，SHA-256为
`2766952041ab8a829dedcc0404a24dd7c22d0b31d3f549cb66752d42d58c315c`。
原扫描保留中國國家圖書館水印；善本书号12072，来源标注为PD-scan。

`additional-source-reading-frozen.json` 是此次同见证的完整助理复读，在
与现存210格录文比较前冻结。此前已知率文、若干例格和七处公式差异的
数量，因此它不是盲读、第二独立专家校勘或另一个原典见证。旧数据曾因
哈希、备份和图像坐标读取而由程序打开；完整复读前未向助理展示其全表
字符串。初次 `sips` 裁图发生中心偏移，最终读格使用原PDF直接裁出的
28幅面板；不能把初次偏移图的坐标元数据当作原页定位证据。

三组年度率矛盾、七格原表／公式端点分歧及疾厄行30名义日空档继续
保留。数值参考不裁定哪条原文正确，不修正录文，不证明民用历日、出生
年龄、出生命度、完整行限、现代天文位置或预测效果。两个实际核心模块
和来源比较库未登记为公开MCP／REST工具，不能用此结果宣称公共果老
功能已全部验收。

`manifest.json` 记录所附文件和原始外部生成器的哈希。参考在实际引擎
比较前冻结；便携生成器只改了输出文件名和本地文件清单，不改计算。
重新生成时，将生成器与两份输入复制到空临时目录，在单独安装了上述
版本的环境运行；原数据文件存在时会拒绝覆盖。生成后应与此处
`reference.json.gz` 逐字节相同。测试直接读取冻结结果，无需安装FLINT。

```bash
uv run --locked --extra dev python -m pytest -q -n 0 tests/guolao/test_guolao_ruler_printed_table.py -k "frozen_nominal or independently_parsed or independent_extreme"
```

## 复验本版与日序

2026-11-25从`c63968b5fe11b59e24a37d8aec4bd2c3d87751ed`的独立检出复验。以本目录的冻结录文和原刊SHA选择`nlc3150_literal210_v1`；不改写七处端点差、疾厄首格之后的30名义日空档或三组年率矛盾。日序从本限一年正月初一的零已过日开始，显式年标按印刷阅读顺序继承，不因月号倒退自动进年；末日的全部子日包含在本格内，下一日为不含端点。这里只能核定这份给定录文的名义映射。

在单独临时目录复制`generate_reference.py`、`arithmetic-inputs.json`和`additional-source-reading-frozen.json`，执行下列命令，其中`$ruler_reference_dir`由调用者设为该目录的绝对路径。生成器拒绝覆盖已有结果；参考重建不增加独立样本数，也没有从生产输出生成预期值。

```bash
uv run --no-project --with python-flint==0.9.0 python -I "$ruler_reference_dir/generate_reference.py"
cmp tests/data/guolao/ruler_flint_v1/reference.json.gz "$ruler_reference_dir/reference.json.gz"
```

实测版本为python-flint 0.9.0／FLINT 3.6.0，重建文件逐字节相同。便携测试检查manifest内四个文件的哈希、生产底本哈希和210格规模，再执行22,635项名义日及子日、210格端点和2项日期压力控制。

远端基线没有提交`tests/fixtures/guolao-ruler-printed-table-v1/`及其引用的24,732,787字节PDF。原扫描及冻结过程的既有完整哈希测试保留为`local_data`，仅在完整档案入口不存在时明确跳过；档案存在但有文件缺失或哈希不符仍失败。该跳过不影响本目录的便携算术验收。另对本机只读原档案的18份附件和PDF复核哈希均相符；旧冻结录文、生产源表与FLINT输入的210格字符串逐项相同。没有取得第二见证或完成独立专家校勘，也不将本机档案加入分发。

同一测试模块通过`tests/support/transports.py`，以固定`as_of=2026-10-12T02:00:00Z`调用公开`astro_guolao_chart`的FastAPI POST、FastMCP工具和CLI，分别核完整响应及严格投影。民用钟、真太阳钟、显式目标时刻与未请求目标时刻分别断言；原尺库没有公开入口，也没有被接入出生排盘。公开小限仍使用其具名底本，研究状态、未定命度／命宿及缺少完整大限仍须保留。三端相等只证明交付一致，不证明名义日到出生年龄或真实历日的转换，也不裁定历史钟制与现实预测。

本轮在共享重测试锁内执行完整分配模块（`-n 0`）：58通过、1跳过，920.55秒；跳过项为外部原扫描档案检查，另有一条Pydantic的`request`别名元数据警告。首轮未设外部档案边界的基线实测为1失败、54通过，失败原因是缺少原扫描回执。全仓Black（3,260文件）、isort、mypy（1,154源文件）、`git diff --check`及调用合同`--check`通过，未复跑公共全量测试。`fatebridge doctor --mcp --family bazi`两次依赖检查通过，但stdio握手均为`TimeoutError`，原因未定；未修改诊断超时。本轮没有真实模型或部署验收。
