"""Selected-text direction for the distinct 四墓土 movement mechanism.

The scanned 子平真诠 PDF44–45 calls this 冲动 rather than 冲克. It
does not give numeric weights, certify formation, or release stored elements.
"""

from copy import deepcopy
from typing import Literal, Mapping, Sequence

from typing_extensions import NotRequired, TypedDict

from fatebridge.core.classical_roots import SOURCE as ROOT_SOURCE
from fatebridge.core.classical_roots import RootSource
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, get_shishen

SOURCE: RootSource = {
    **ROOT_SOURCE,
    "id": "ziping_storage_movement_v1",
    "title": "秘本子平真诠·论墓库刑冲之说",
    "pdf_pages": [44, 45],
    "printed_pages": [35, 36],
}
CLASHES = {frozenset("辰戌"), frozenset("丑未")}


class StorageRootRetention(TypedDict):
    pillar: str
    branch: str
    stem: str
    element: str
    ten_god: str
    event_retention_multiplier: float
    basis: str
    combined_loss_multiplier: NotRequired[float]
    remaining_hidden_mass: NotRequired[float]


class StorageMovementReceipt(TypedDict):
    method_id: Literal["ziping_storage_movement_v1"]
    movement_kind: Literal["same_element_earth_movement"]
    root_effects: list[StorageRootRetention]
    earth_energy_bonus: float
    water_retention_policy: float
    numeric_magnitude_origin: Literal["engineering_policy_not_classical_coefficient"]
    formation_status: Literal["not_adjudicated"]
    source: RootSource
    scope: str


def storage_movement_effect(
    branches: Mapping[str, str],
    positions: Sequence[str],
    kind: str,
    day_stem: str,
    water_retention: float,
) -> StorageMovementReceipt | None:
    """Separate the text's retention direction from the numeric policy for participating roots."""
    present = frozenset(branches[p] for p in positions)
    applicable = (kind == "六冲" and len(positions) == 2 and present in CLASHES) or (
        kind == "刑" and present == frozenset("丑未戌")
    )
    if not applicable:
        return None
    retention = min(1.0, max(0.0, water_retention))
    return {
        "method_id": "ziping_storage_movement_v1",
        "movement_kind": "same_element_earth_movement",
        "root_effects": [
            {
                "pillar": name,
                "branch": branches[name],
                "stem": stem,
                "element": STEM_ELEMENTS[stem][0].value,
                "ten_god": get_shishen(day_stem, stem),
                "event_retention_multiplier": (
                    retention if STEM_ELEMENTS[stem][0].value == "水" else 1.0
                ),
                "basis": (
                    "earth_movement_water_control_engineering_retention"
                    if STEM_ELEMENTS[stem][0].value == "水"
                    else "no_automatic_root_damage_or_release_by_this_event"
                ),
            }
            for name in positions
            for stem in BRANCH_HIDDEN_STEMS[branches[name]]
        ],
        "earth_energy_bonus": 0.0,
        "water_retention_policy": retention,
        "numeric_magnitude_origin": "engineering_policy_not_classical_coefficient",
        "formation_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": "本事件按所选原典保留土根，不自动增土或释放金木水火；土动对参与支水根的减损幅度沿用工程参数。未裁定全局制化、透干财官是否有效或成格。其他合绊、刑冲仍分别作用。",
    }
