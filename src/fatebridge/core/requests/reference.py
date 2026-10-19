"""Request contracts for reference."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from fatebridge.core.requests.base import _DeferredModel


class ExportRegistryRequest(_DeferredModel):
    """Request model for export registry lookup."""

    technique: Optional[str] = Field(default=None, description="Optional technique key")


class ExportParseRequest(_DeferredModel):
    """Request model for export snapshot parsing."""

    technique: str = Field(description="Technique key, e.g. qimen")
    content: str = Field(description="Snapshot text content")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional selected section titles",
    )
    planet_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional planet info export toggles",
    )
    astro_meaning: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional astro meaning export toggles",
    )


class KnowledgeRegistryRequest(_DeferredModel):
    """Request model for bundled knowledge registry."""

    domain: Optional[str] = Field(default=None, description="Optional domain filter")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class KnowledgeReadRequest(_DeferredModel):
    """Request model for bundled knowledge lookup."""

    domain: str = Field(
        description=(
            "知识域：astro / bazi / liureng / qimen。各域适用字段不同——"
            "astro：key，或 category=aspect 配合 aspect_degree；"
            "星体对 object_a/object_b 只给相位条目标注对象，不能单独定位词条；"
            "bazi / qimen：key（category 可省略，自动解析）；"
            "liureng：(jiang_name, tian_branch, di_branch)。"
        )
    )
    category: Optional[str] = Field(
        default=None,
        description=(
            "Category within the domain. Optional: if omitted, it is auto-resolved "
            "from `key` (astro/bazi/qimen only). For an astro aspect_degree "
            "query without key, explicitly pass category='aspect'."
        ),
    )
    key: Optional[str] = Field(default=None, description="Primary lookup key")
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )
    aspect_degree: Optional[int] = Field(
        default=None,
        description="[domain=astro, category=aspect] 相位角度；无 key 时须显式提供 category=aspect",
    )
    object_a: Optional[str] = Field(
        default=None, description="[domain=astro] 第一星体（相位查询）"
    )
    object_b: Optional[str] = Field(
        default=None, description="[domain=astro] 第二星体（相位查询）"
    )
    jiang_name: Optional[str] = Field(
        default=None, description="[domain=liureng] 贵神名"
    )
    tian_branch: Optional[str] = Field(
        default=None, description="[domain=liureng] 天盘地支"
    )
    di_branch: Optional[str] = Field(
        default=None, description="[domain=liureng] 地盘地支"
    )
