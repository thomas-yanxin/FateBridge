"""Historical envelopes keep their exact, unaccepted current-schema boundary."""

import pytest

from fatebridge.application.execution import OutputContractError, validate_output

NOMINAL_SEASONAL_GAP = "完整三合局体须保留同次月建及三传的名义季态与可空事实"


def assert_historical_contract_gap(spec, value):
    with pytest.raises(OutputContractError) as error:
        validate_output(spec, value)
    assert str(error.value.__cause__) == NOMINAL_SEASONAL_GAP
