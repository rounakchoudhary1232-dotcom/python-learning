# ULTRON paper trading foundation

ULTRON's trading module is **PAPER only**. It has no broker adapter, live-order endpoint, or broker credential configuration.

## Phase 1 market intelligence

`MarketContext` is a read-only, serializable analysis result built from validated OHLCV candles. Candles must have finite values, valid OHLC ranges, non-negative volume, and strictly ordered unique timestamps. The current simulated provider includes symbol and timeframe on every candle and is explicitly labelled `SIMULATED`.

The analysis flow is: validated candles → EMA/RSI/ATR features → swing highs/lows → HH/HL/LH/LL structure, BOS and CHOCH evidence → nearest support/resistance → volatility state → breakout/reversal evidence → multi-timeframe summary → regime. Structure is descriptive evidence, not a prediction. Volatility states are `LOW`, `NORMAL`, `HIGH`, and `EXTREME`; regimes are `TRENDING_BULL`, `TRENDING_BEAR`, `RANGE`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`, or `UNCLEAR`.

`GET /api/v1/trading/market-context/{symbol}` is authenticated and read-only. It returns the complete context and never executes a trade. For the simulated provider, 1h/5m/1m deterministic series supply higher/trading/lower timeframe analysis. Real providers must return actual data; missing data is reported as invalid/insufficient rather than fabricated.

```text
Simulated market data -> indicators/features -> regime + strategy signal
                         -> deterministic risk/kill-switch check -> paper trade journal
                         -> walk-forward backtest metrics
```

`GET /api/v1/trading/status` reports the paper account. `POST /decision/{symbol}` produces an explainable decision without trading. `POST /paper/execute/{symbol}` records only an approved deterministic PAPER decision. `POST /kill-switch?enabled=true` immediately rejects new decisions. `GET /backtest/{symbol}` runs an explicitly labelled historical simulation using only prior candles for each decision.

The default `DATA_PROVIDER=simulated` uses deterministic development candles and is never presented as live data. A future data provider implements `MarketDataProvider`; a future broker would require a distinct, deliberately designed live safety boundary.

Safe configuration defaults are in `.env.example`: `TRADING_MODE=PAPER`, a 1% per-trade risk cap, 3% daily loss cap, five daily trades, 0.60 minimum confidence, and 1.5 minimum risk/reward. Backtest results are research measurements, not proof of future performance.

## Phase 2 strategy intelligence

Phase 2 is read-only: `MarketContext → regime compatibility → strategy registry → evaluation → normalized signal`. It has no broker, order, position, provider, database, or risk-control side effects. The five registered strategies are trend following (trending regimes), momentum (directional/high-volatility regimes), breakout (trend/volatility conditions), mean reversion (range/low-volatility), and volatility breakout (volatility regimes).

Every signal contains `strategy_name`, `signal` (`BUY`, `SELL`, `HOLD`, or `REJECT`), `score`, `evidence`, `regime_compatible`, and relevant `factors`. `score` is deterministic evidence strength only: it is not a probability, guaranteed win rate, profitability claim, or execution instruction. Existing PAPER approval, kill-switch, and risk controls remain the execution boundary.
