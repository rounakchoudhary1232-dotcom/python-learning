# ULTRON paper trading foundation

ULTRON's trading module is **PAPER only**. It has no broker adapter, live-order endpoint, or broker credential configuration.

```text
Simulated market data -> indicators/features -> regime + strategy signal
                         -> deterministic risk/kill-switch check -> paper trade journal
                         -> walk-forward backtest metrics
```

`GET /api/v1/trading/status` reports the paper account. `POST /decision/{symbol}` produces an explainable decision without trading. `POST /paper/execute/{symbol}` records only an approved deterministic PAPER decision. `POST /kill-switch?enabled=true` immediately rejects new decisions. `GET /backtest/{symbol}` runs an explicitly labelled historical simulation using only prior candles for each decision.

The default `DATA_PROVIDER=simulated` uses deterministic development candles and is never presented as live data. A future data provider implements `MarketDataProvider`; a future broker would require a distinct, deliberately designed live safety boundary.

Safe configuration defaults are in `.env.example`: `TRADING_MODE=PAPER`, a 1% per-trade risk cap, 3% daily loss cap, five daily trades, 0.60 minimum confidence, and 1.5 minimum risk/reward. Backtest results are research measurements, not proof of future performance.
