# 四柱、年柱、月柱知识查询

三个词条可由 `knowledge_read` 的 `domain=bazi` 和中文 `key` 直接查询；也可显式指定 `category=basics`。`knowledge_registry` 会列出该分类的三个键。

普通 CLI 查询：

```bash
uv run --locked --extra dev python -m fatebridge.cli knowledge_read \
  --domain bazi --key 四柱 \
  --fields title lines citation provenance.entry_curation.source_refs \
  --strict-fields --include-snapshot-text false
```

将 `--key` 改为 `年柱` 或 `月柱` 即可查询另外两条。MCP 使用相同参数，例如：

```json
{
  "domain": "bazi",
  "key": "月柱",
  "fields": ["title", "lines", "citation", "provenance.entry_curation.source_refs"],
  "strict_fields": true,
  "include_snapshot_text": false
}
```

REST 使用知识查询的 POST 接口，正文传入 `domain`、`key` 和可选的 `category`；字段投影和快照选项按[API 文档](api-reference.md)放在查询参数中。三端返回相同词条正文与来源信息，运行回执分别保留。

## 来源与范围

原典背景来自萬民英《三命通會》四庫全書本卷二〈論年月日時〉及〈論遁月時〉的[维基文库固定修订 761691](https://zh.wikisource.org/w/index.php?title=%E4%B8%89%E5%91%BD%E9%80%9A%E6%9C%83%20%28%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC%29/%E5%8D%B702&oldid=761691)。来源清单（本地数据：`../tests/fixtures/bazi_foundations_v1/source-manifest.json`）保留完整数字转录、原 API 回执及散列；整理记录（本地数据：`../tests/fixtures/bazi_foundations_v1/curation-review.json`）保留选段位置和逐句归属。数字转录核对不等于书影校勘或独立专家审定。

词条的 `provenance.entry_curation` 分别列出原典选段、当前实现和解释边界对应的行号索引。八字年界、节月边界及月干取法由当前程序实现另行归属，不把程序约定冒充所有传统流派的统一原文，也不采用相邻古文中的寿命或现实遭遇断语。

实现引用保留审阅源码快照的整文件散列，同时按函数文本散列和十二节月映射核对现版。这样可核对具体规则，而不会把无关源码行的变化误认为词条依据已经改变；相关函数或月界映射改变时仍须重新审阅。

这是独立补充知识组件：旧基础包的 85 条知识、索引和整理台账保留原字节；新增三条由运行时合并，并在 `provenance.supplements` 列出组件版本、文件散列与分类。历史基础包计数不作为合并后的总计。

概念查询不需要出生资料，不触发个人排盘；词条可复核也不证明现实预测有效。接口参数见[API 文档](api-reference.md)，完整 MCP 参数以当前连接的工具 Schema 为准。

本轮三端、构建包和真实模型的结果及保留失败见验收记录（本地数据：`validation/bazi-foundations-knowledge-v1.md`）。

后续十条格局词条的实现绑定及失效文档链接修复见后续修复记录（本地数据：`validation/bazi-knowledge-binding-and-links-v1.md`）；原验收记录保留首次结果。
