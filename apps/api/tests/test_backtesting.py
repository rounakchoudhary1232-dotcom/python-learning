import pytest
from app.services.backtesting import BacktestConfig,BacktestEngine,WalkForwardConfig,split_historical_candles,walk_forward_windows
from app.services.backtesting import EquityPoint, _max_drawdown_absolute
from app.services.trading import SimulatedMarketDataProvider
def test_backtest_is_deterministic_research_only_and_validates_input():
 c=SimulatedMarketDataProvider().candles("SPY","5m",60);a=BacktestEngine().run("SPY","5m",c);b=BacktestEngine().run("SPY","5m",c)
 assert a.payload()==b.payload() and a.paper_only and a.research_only and a.valid
 assert not BacktestEngine().run("SPY","5m",c[:5]).valid
def test_next_open_entries_and_zero_cost_warning():
 r=BacktestEngine().run("SPY","5m",SimulatedMarketDataProvider().candles("SPY","5m",60),BacktestConfig())
 assert "zero-cost simulation" in r.warnings
 assert all(t.entry_timestamp for t in r.trades)
def test_historical_strategy_signals_are_retained_without_future_context():
 c=SimulatedMarketDataProvider().candles("SPY","5m",60);r=BacktestEngine().run("SPY","5m",c)
 assert r.strategy_research and all("signals" in point and point["signals"] for point in r.strategy_research)
def test_historical_decision_engine_results_are_retained_read_only():
 r=BacktestEngine().run("SPY","5m",SimulatedMarketDataProvider().candles("SPY","5m",60))
 assert all(point["decision"]["action"] in {"BUY","SELL","HOLD","REJECT"} for point in r.strategy_research)
def test_risk_assessments_are_retained_for_historical_candidates():
 r=BacktestEngine().run("SPY","5m",SimulatedMarketDataProvider().candles("SPY","5m",60))
 assert all("risk" in point for point in r.strategy_research if point["decision"]["action"] in {"BUY","SELL"})
def test_strategy_and_regime_statistics_are_safe_and_descriptive():
 r=BacktestEngine().run("SPY","5m",SimulatedMarketDataProvider().candles("SPY","5m",60))
 assert isinstance(r.strategy_statistics,dict) and isinstance(r.regime_statistics,dict)
 assert all("trade_count" in value and "average_r" in value for value in r.regime_statistics.values())
def test_historical_split_is_chronological_deterministic_and_safe():
 candles=SimulatedMarketDataProvider().candles("SPY","5m",10);original=list(candles);ins,oos=split_historical_candles(candles,.8)
 assert len(ins)==8 and len(oos)==2 and ins+oos==candles and candles==original and split_historical_candles(candles,.8)==(ins,oos)
 with pytest.raises(ValueError):split_historical_candles(candles,1)
 with pytest.raises(ValueError):split_historical_candles(candles[:1],.8)
def test_split_backtest_keeps_in_sample_isolated_from_later_candles():
 candles=SimulatedMarketDataProvider().candles("SPY","5m",120);config=BacktestConfig(split_ratio=.8);first=BacktestEngine().run("SPY","5m",candles,config)
 changed=list(candles);changed[-1]=changed[-1].__class__(changed[-1].timestamp,changed[-1].open,changed[-1].high,changed[-1].low,changed[-1].close+10,changed[-1].volume,changed[-1].symbol,changed[-1].timeframe);second=BacktestEngine().run("SPY","5m",changed,config)
 assert first.split_ratio==.8 and first.in_sample==second.in_sample and first.out_of_sample
def test_walk_forward_windows_are_chronological_and_deterministic():
 candles=SimulatedMarketDataProvider().candles("SPY","5m",20);windows=walk_forward_windows(candles,WalkForwardConfig(10,5,5))
 assert len(windows)==2 and windows[0][0][-1].timestamp<windows[0][1][0].timestamp and windows==walk_forward_windows(candles,WalkForwardConfig(10,5,5))
 with pytest.raises(ValueError):walk_forward_windows(candles,WalkForwardConfig(0,5,5))
def test_walk_forward_executes_each_complete_test_window_deterministically():
 candles=SimulatedMarketDataProvider().candles("SPY","5m",80);engine=BacktestEngine();cfg=WalkForwardConfig(30,25,15)
 result=engine.walk_forward("SPY","5m",candles,cfg);again=engine.walk_forward("SPY","5m",candles,cfg)
 assert len(result)==2 and result==again and result[0]["train_end"]<result[0]["test_start"] and result[0]["result"]["research_only"]
def test_extended_metrics_are_present_and_deterministic():
 r=BacktestEngine().run("SPY","5m",SimulatedMarketDataProvider().candles("SPY","5m",60));m=r.metrics
 assert {"max_drawdown_absolute","maximum_drawdown_duration","consecutive_wins","breakeven_trades","average_win","sharpe_like"}<=set(m)
def test_absolute_drawdown_uses_starting_and_running_peak_equity():
 assert _max_drawdown_absolute(10000,[EquityPoint("a",9000,.1),EquityPoint("b",11000,0),EquityPoint("c",9900,.1)])==1100
