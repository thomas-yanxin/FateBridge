# 贡献指南

FateBridge 接受算法、接口、测试、文档和场景技能改进。开发命令与架构约束集中在 [开发指南](docs/development-guide.md)，本页说明协作和提交流程。

## 开始贡献

先检查已有 [Issues](https://github.com/Yonder-Lab/FateBridge/issues) 和 Pull Requests，避免重复工作。范围较大的新能力或接口变更先在 Issue 中说明用例、输入输出与兼容策略。文档修正可直接准备 PR。

外部贡献者 Fork 后创建分支；已有仓库写权限者可在自己的工作分支开发：

```bash
git clone https://github.com/YOUR_USERNAME/FateBridge.git
cd FateBridge
git remote add upstream https://github.com/Yonder-Lab/FateBridge.git
git fetch upstream
git switch -c codex/your-change upstream/master
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

没有 uv 时使用 `python3.12 -m venv .venv`，激活后执行 `python -m pip install -e ".[dev]"`。Windows 环境命令见 [快速入门](docs/getting-started.md)。PR 目标分支为 `master`。

## 报告问题

Bug 报告请提供实际版本/提交、Python 与依赖版本、操作系统、最小请求或 CLI 命令、预期结果与实际结果。涉及精度时附上时区、坐标、太阳时策略、分析日期和星历模型；脱敏姓名、生日与密钥。区分运行时缺依赖、模型校验失败和算法结果偏差。

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不在公开 Issue 中粘贴敏感复现材料。

## 修改约束

- 工具定义位于 `services/catalog/`，由 `services/tool_catalog.py` 有序装配为唯一 `CATALOG`；请求模型位于 `core/requests/`。领域逻辑放在 `core` / `analysis` / `services`，不要在 transport 内复制算法。
- 输入归一化、星历共享状态、快照导出复用现有公共实现。接口或默认值变化要检查 REST / MCP / CLI 的差异。
- 算法修复提供有依据的边界/回归用例；不能用“更新黄金快照”替代正确性验证。黄金字节基线仅在指定参考平台上更新。
- 文档职责与同步范围见 [文档维护与验证](docs/development-guide.md#文档维护与验证)。涉及技能工具或输入时同步 `agents/interface.yaml`。
- Python 代码遵循现有格式与类型约定；提交中保留无关工作，不进行顺带的大面积改写。

## 提交前验证

代码变更运行与 CI 对齐的检查：

```bash
python -m pytest -q
black --check src/fatebridge scripts tests
isort --check-only src/fatebridge scripts tests
mypy src/fatebridge/
git diff --check
```

纯文档变更运行 `python scripts/check_docs.py` 与[文档合同和示例检查](docs/development-guide.md#文档维护与验证)；修改生成源后重新生成并检查派生文件。报告实际测试结果与跳过项，不将本地通过写成 CI 已通过。

版本与数据打包变更还需检查 `pyproject.toml`、版本常量、CHANGELOG 和 wheel 的数据文件；发布流程见 [开发指南](docs/development-guide.md#ci打包与发布)。

## 提交与 Pull Request

先检查工作区，再只暂存本次改动：

```bash
git status --short
git diff
git add <本次修改的文件>
git commit -m "docs: clarify integration contracts"
git push -u origin codex/your-change
```

提交信息使用 `feat`、`fix`、`docs`、`refactor`、`perf`、`test` 或 `chore` 等类型，可加范围。PR 描述说明：

- 具体问题及修改后的行为；
- 相关 Issue（如有）；
- 测试/示例的实际结果、兼容影响与未验证边界。

审查反馈处理后，继续推送同一分支。不要在共享工作分支上为同步上游而重置或覆盖他人的改动。

## 保持 Fork 同步

工作区干净时更新本地 `master`；若已产生本地提交且无法快进，先审查差异再决定如何合并：

```bash
git fetch upstream
git switch master
git merge --ff-only upstream/master
git push origin master
```

回到工作分支后，根据团队约定合并或 rebase。协作中尊重不同观点，反馈聚焦问题本身，不发布他人的私人信息。
