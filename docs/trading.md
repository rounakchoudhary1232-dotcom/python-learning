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

## Phase 3 decision engine

The read-only Decision Engine aggregates compatible Phase 2 signals into one `BUY`, `SELL`, `HOLD`, or `REJECT` intelligence result. Its deterministic pipeline validates context and PAPER/kill-switch constraints, aggregates compatible directional evidence, detects conflicts, applies MTF alignment or conflict adjustment, checks the bounded evidence score against configuration, and validates expected R:R when valid levels exist. It returns entry, stop, target and R:R only when determinable.

Confidence is an explainable 0.0–1.0 evidence score, not a guaranteed probability or profitability claim. The engine never orders, changes balances or positions, or bypasses risk. Risk and paper execution remain separate authoritative boundaries.

## Phase 4 risk and paper-execution safety

`Decision → Risk Assessment → Paper Execution` keeps safety authoritative. Risk assessment validates PAPER mode, kill switch, valid directional SL/TP, R:R, sizing (`equity × max_risk_per_trade / abs(entry - stop)`), daily loss, trade count, drawdown, exposure, consecutive losses, duplicate positions, and available timestamp freshness. Rejections are explicit and no strategy or AI/LLM result can override them. This phase does not enable live trading or a broker.

## Phase 5 paper monitoring

Paper positions can be monitored through `POST /api/v1/trading/paper/monitor/{symbol}`. It only checks existing PAPER positions against the current simulated closing price and closes SL/TP exits deterministically. BUY P&L is `(exit - entry) × quantity`; SELL P&L is `(entry - exit) × quantity`. The kill switch blocks entries but not protective exits. There is no broker, daemon, tick ordering, fee, or slippage model; an intrabar candle that reaches both levels must be treated conservatively as SL first. Phase 5 does not enable live trading.

## Phase 6 backtesting research

`BacktestEngine` is a PAPER/RESEARCH-only chronological simulator. It validates historical candles, derives each signal from candles available through N, and enters only at N+1 open. SL is checked before TP when both touch in one OHLC candle. Fees and slippage are deterministic configuration rates; zero-cost runs are explicitly warned. Results include trades, an equity curve, net P&L, drawdown, profit factor, expectancy, average R, and small-sample warnings. Backtest results are historical simulations and do not guarantee future performance. Win rate alone is not sufficient to evaluate a strategy.

Completed backtest trades are also grouped as `strategy_statistics` and `regime_statistics`. Attribution uses the selected strategies and actual regime retained at the original decision point; no signals or regimes are recalculated. These statistics describe historical backtest behavior and do not guarantee future performance.

Walk-forward windows are chronological train/test partitions advanced by a configured step size; no test window informs its prior train window and no automatic optimization occurs. Walk-forward results are historical research results and do not guarantee future performance.

Each complete walk-forward test window is now executed through the existing `BacktestEngine`; train ranges are retained as historical window metadata only. This is research evaluation only and does not select parameters or execute trades externally.

## Phase 7 execution-cost model

The reusable research cost model applies deterministic adverse slippage to execution prices and fees to executed notional (`price × quantity × fee_rate`), with an optional minimum fee. BUY entries and SELL exits slip upward; BUY exits and SELL entries slip downward. It is a simulation utility only: it has no broker, live execution, or external-account integration.

## Phase 7.2 realistic backtest fills

Backtests now use that cost model after candle OHLC determines an SL/TP trigger: the trigger remains the reference market price, while the simulated fill receives directional adverse slippage and entry/exit fees. Trade journals retain both reference and fill prices, fees, total execution cost, gross P&L, and net P&L. Equity and research metrics use net P&L. The default remains zero-cost compatible, and this remains research simulation with no live broker execution.
