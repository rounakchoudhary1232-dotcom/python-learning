import math
import pytest
from app.services.execution_costs import ExecutionCostConfig, ExecutionCostModel


def model(): return ExecutionCostModel(ExecutionCostConfig(fee_rate=.001, slippage_bps=10))


def test_directional_adverse_slippage_for_entries_and_exits():
    costs = model()
    assert costs.execution_price("BUY", 100, True) == 100.1
    assert costs.execution_price("BUY", 100, False) == 99.9
    assert costs.execution_price("SELL", 100, True) == 99.9
    assert costs.execution_price("SELL", 100, False) == 100.1


def test_zero_costs_fee_and_round_trip_total_are_deterministic():
    zero = ExecutionCostModel()
    assert zero.execution_price("BUY", 100, True) == 100 and zero.fee(100, 3) == 0
    cost = model().round_trip("BUY", 100, 110, 2)
    assert cost.entry_fee == .2002 and cost.exit_fee == .21978
    assert cost.total_cost == pytest.approx(.2 + .22 + .2002 + .21978)
    assert cost == model().round_trip("BUY", 100, 110, 2)


def test_invalid_configurations_and_inputs_are_rejected():
    with pytest.raises(ValueError): ExecutionCostConfig(fee_rate=-.1)
    with pytest.raises(ValueError): ExecutionCostConfig(slippage_bps=math.inf)
    with pytest.raises(ValueError): model().round_trip("BUY", math.nan, 100, 1)
    with pytest.raises(ValueError): model().execution_price("HOLD", 100, True)
