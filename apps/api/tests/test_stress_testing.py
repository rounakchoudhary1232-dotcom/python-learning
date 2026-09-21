from dataclasses import replace
import pytest
from app.services.backtesting import BacktestConfig, BacktestEngine
from app.services.data_quality import DataQualityConfig
from app.services.execution_costs import ExecutionCostConfig
from app.services.stress_testing import StressScenario, StressTester
from app.services.trading import SimulatedMarketDataProvider

def candles(): return SimulatedMarketDataProvider().candles("SPY", "5m", 80)
def run(scenario): return StressTester().run(scenario)
def test_extreme_range_gap_and_zero_volume_invariants():
 data=candles();data[30]=replace(data[30],high=data[30].high*2,low=data[30].low*.5)
 assert run(StressScenario("extreme","SPY","5m",data,minimum_trades=1)).passed
 gap=candles();del gap[30];cfg=BacktestConfig(data_quality=DataQualityConfig(expected_timeframe="5m"))
 assert run(StressScenario("gap","SPY","5m",gap,cfg,required_quality_warning="timeframe_gap",minimum_trades=1)).passed
 zero=candles();zero[10]=replace(zero[10],volume=0)
 assert run(StressScenario("zero_volume","SPY","5m",zero,required_quality_warning="zero_volume",minimum_trades=1)).passed
def test_strict_gap_and_risk_limits_produce_meaningful_rejections():
 gap=candles();del gap[20];strict=BacktestConfig(data_quality=DataQualityConfig(expected_timeframe="5m",strict_gaps=True))
 assert run(StressScenario("strict_gap","SPY","5m",gap,strict,expect_valid=False,required_reason="timestamp interval differs from expected timeframe")).passed
 risk_candles=SimulatedMarketDataProvider().candles("SPY","5m",200)
 assert run(StressScenario("risk_limit","SPY","5m",risk_candles,minimum_rejections=1,required_reason="max trades per day reached")).passed
def test_cost_drawdown_sizes_and_conservative_sl_first_are_measurable():
 baseline=run(StressScenario("baseline","SPY","5m",candles(),minimum_trades=1));high=run(StressScenario("cost","SPY","5m",candles(),BacktestConfig(execution_costs=ExecutionCostConfig(fee_rate=.02,slippage_bps=100)),minimum_trades=1,minimum_execution_cost=.01))
 assert high.passed and high.net_pnl<baseline.net_pnl
 assert run(StressScenario("tiny","SPY","5m",candles(),BacktestConfig(initial_balance=.01),minimum_trades=1)).passed
 assert run(StressScenario("large","SPY","5m",candles(),BacktestConfig(initial_balance=1_000_000),minimum_trades=1)).passed
 data=candles();first=BacktestEngine().run("SPY","5m",data).trades[0];index=next(i for i,c in enumerate(data) if c.timestamp.isoformat()==first.entry_timestamp);data[index]=replace(data[index],high=data[index].high*2,low=data[index].low*.5)
 assert run(StressScenario("both","SPY","5m",data,minimum_trades=1,required_exit_reason="EXIT_SL")).passed
def test_repeatability_and_invalid_configuration():
 scenario=StressScenario("repeat","SPY","5m",candles(),minimum_trades=1)
 assert run(scenario)==run(scenario)
 with pytest.raises(ValueError): run(StressScenario("",candles=candles()))
