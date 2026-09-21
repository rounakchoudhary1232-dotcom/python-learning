from dataclasses import replace
from datetime import timedelta
from app.services.backtesting import BacktestEngine
from app.services.data_quality import DataQualityConfig,validate_historical_data
from app.services.trading import SimulatedMarketDataProvider
def candles():return SimulatedMarketDataProvider().candles("SPY","5m",30)
def test_valid_data_and_zero_volume_warning_are_serializable():
 report=validate_historical_data(candles(),DataQualityConfig(expected_timeframe="5m"));assert report.valid and report.payload()["checked_candles"]==30
 zero=list(candles());zero[0]=replace(zero[0],volume=0);assert validate_historical_data(zero).warnings[0]["code"]=="zero_volume"
def test_invalid_ohlc_timestamp_numeric_and_history_are_fatal():
 data=candles();bad=list(data);bad[1]=replace(bad[1],high=0);assert not validate_historical_data(bad).valid
 assert not validate_historical_data(data+[data[-1]]).valid
 assert not validate_historical_data(data[:2],DataQualityConfig(minimum_history=3)).valid
def test_backtest_rejects_fatal_quality_before_simulation():
 bad=list(candles());bad[1]=replace(bad[1],close=float("nan"));result=BacktestEngine().run("SPY","5m",bad)
 assert not result.valid and result.data_quality["errors"] and not result.trades
