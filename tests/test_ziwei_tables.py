import pytest

from fatebridge.core.ziwei_tables import (
    ZIWEI_STAR_BRIGHTNESS,
    lookup_star_brightness,
    split_star_mutagen,
)


def test_table_shape_is_twelve_per_star():
    for star, row in ZIWEI_STAR_BRIGHTNESS.items():
        assert len(row) == 12, f"{star} must have 12 branch entries"


def test_lookup_known_iztro_software_cells():
    # 寅-indexed: 寅=0, 午=4, 丑=11 (ZIWEI_BRANCH_SEQUENCE order)
    assert lookup_star_brightness("紫微", "午") == "庙"  # ziweiMaj[4]=miao
    assert lookup_star_brightness("紫微", "寅") == "旺"  # ziweiMaj[0]=wang
    assert lookup_star_brightness("太阳", "戌") == "不"  # taiyangMaj[8]=bu
    assert lookup_star_brightness("天机", "未") == "陷"  # tianjiMaj[5]=xian


def test_lookup_unknown_or_empty_returns_none():
    assert lookup_star_brightness("天魁", "子") is None  # not in table
    assert lookup_star_brightness("擎羊", "寅") is None  # qingyangMin[0]=''
    assert lookup_star_brightness("陀罗", "卯") is None  # tuoluoMin[1]=''
    assert lookup_star_brightness("紫微", "辰X") is None  # bad branch


def test_split_star_mutagen():
    assert split_star_mutagen("紫微化科") == ("紫微", "化科")
    assert split_star_mutagen("太阴化忌") == ("太阴", "化忌")
    assert split_star_mutagen("天府") == ("天府", None)
    assert split_star_mutagen("") == ("", None)
