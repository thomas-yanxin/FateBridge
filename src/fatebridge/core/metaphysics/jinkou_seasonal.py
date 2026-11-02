"""Jin Kou's declared month convention, separate from internal/day strength.

CNTS volume 1, PDF pages 76–77, supplies the 25 seasonal cells. Mapping all
of 辰未戌丑 to soil remains the existing convention, not an adjudication of
the last-eighteen-days alternative.
"""

from ...utils.data import EARTHLY_BRANCHES
from .common import branch_element_text, status_against_anchor


def seasonal_power(month_branch: str, element: str) -> str:
    if (
        month_branch not in EARTHLY_BRANCHES
        or element not in "木火土金水"
        or len(element) != 1
    ):
        raise ValueError("四季旺衰须使用月建支及四位实际五行")
    return status_against_anchor(branch_element_text(month_branch), element)


def seasonal_power_basis(month_branch: str) -> str:
    if month_branch not in EARTHLY_BRANCHES:
        raise ValueError("四季旺衰须使用月建支")
    phase = branch_element_text(month_branch)
    return (
        f"五行休旺：按月建{month_branch}之{phase}气，辰戌丑未按土旺月；不以地分定季节"
    )
