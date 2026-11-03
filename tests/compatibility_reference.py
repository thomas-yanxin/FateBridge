"""Current v11 provenance with the unchanged independent score ledgers.

The original helper remains sealed as historical evidence. Its numeric checks
are reused verbatim after separately checking the actual current method ID.
"""

from copy import deepcopy

from tests.fixtures.compatibility import (
    CURRENT_STRENGTH_METHOD_ID as HISTORICAL_STRENGTH_METHOD_ID,
)
from tests.fixtures.compatibility import CURRENT_VERSION, REFERENCE
from tests.fixtures.compatibility import (
    assert_score_reference as historical_score_reference,
)
from tests.fixtures.compatibility import reference_dimensions, reference_total

CURRENT_STRENGTH_METHOD_ID = "season_root_revelation_relations_v11"


def assert_score_reference(summary, detailed_analysis=None, kind="general"):
    historical = deepcopy(summary)
    for person in ("person1", "person2"):
        assert summary["scoring"]["input_methods"][person]["strength_method_id"] == (
            CURRENT_STRENGTH_METHOD_ID
        )
        historical["scoring"]["input_methods"][person][
            "strength_method_id"
        ] = HISTORICAL_STRENGTH_METHOD_ID
    historical_score_reference(historical, detailed_analysis, kind)
