"""Request contracts for reference."""

from __future__ import annotations

from pydantic import Field

from fatebridge.core.requests.base import _DeferredModel


class KnowledgeRegistryRequest(_DeferredModel):
    """Request model for bundled knowledge registry."""

    domain: str | None = Field(
        default=None,
        description="Optional domain filter: astro/bazi/liureng/qimen/heluo/canping/human_design. Heluo/Canping/Human Design expose source-bound partial references; catalogues do not select rules applicable to a person. Human Design retains384line locators; actual coverage reports pending local paraphrases, uncurated meanings and independent acceptance separately. Omit for all domains with separate source provenance.",
    )


class KnowledgeReadRequest(_DeferredModel):
    """Request model for bundled knowledge lookup."""

    domain: str = Field(
        description=(
            "知识域：astro / bazi / liureng / qimen / heluo / canping / human_design。各域适用字段不同——"
            "astro：key，或 category=aspect 配合 aspect_degree；"
            "星体对 object_a/object_b 只给相位条目标注对象，不能单独定位词条；"
            "bazi / qimen：key（category 可省略，自动解析）；"
            "liureng：(jiang_name, tian_branch, di_branch)。"
            "heluo/canping：按 knowledge_catalog 的 category 和 key 读取具名来源，也可自动解析唯一 key。"
            "这些是参考原文及政策角色，不替代同run排盘适用性回执。"
            "human_design：category=lines，key=门.线，例如1.1；384线定位，整理与独立复核数见目录coverage，未整理爻义为null。保留来源条件及未知适用性，不得仅凭参考选定个人固定极性。"
        )
    )
    category: str | None = Field(
        default=None,
        description=(
            "Category within the domain. Optional: if omitted, it is auto-resolved "
            "from `key` (astro/bazi/qimen/heluo/canping/human_design). For an astro aspect_degree "
            "query without key, explicitly pass category='aspect'."
        ),
    )
    key: str | None = Field(default=None, description="Primary lookup key")
    aspect_degree: int | None = Field(
        default=None,
        description="[domain=astro, category=aspect] 相位角度；无 key 时须显式提供 category=aspect",
    )
    object_a: str | None = Field(
        default=None, description="[domain=astro] 第一星体（相位查询）"
    )
    object_b: str | None = Field(
        default=None, description="[domain=astro] 第二星体（相位查询）"
    )
    jiang_name: str | None = Field(default=None, description="[domain=liureng] 贵神名")
    tian_branch: str | None = Field(
        default=None, description="[domain=liureng] 天盘地支"
    )
    di_branch: str | None = Field(default=None, description="[domain=liureng] 地盘地支")
