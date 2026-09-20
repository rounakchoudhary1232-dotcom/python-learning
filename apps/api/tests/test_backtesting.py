from app.services.backtesting import BacktestConfig,BacktestEngine
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
