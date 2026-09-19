"""Deterministic, paper-only trading research and simulation primitives.

No broker credentials or live order adapter exists in this module.  Signals are
research outputs; deterministic risk checks make the final paper-execution
decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import math
import uuid
from typing import Protocol


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Decision:
    decision_id: str
    symbol: str
    timeframe: str
    regime: str
    strategy: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    quantity: float
    risk_amount: float
    risk_reward_ratio: float
    score: int
    confidence: float
    supporting_factors: list[str]
    contradicting_factors: list[str]
    rejected_rules: list[str]
    final_decision: str

    def payload(self) -> dict:
        return asdict(self)


class MarketDataProvider(Protocol):
    name: str
    def candles(self, symbol: str, timeframe: str, limit: int = 120) -> list[Candle]: ...


class SimulatedMarketDataProvider:
    """Deterministic development data, always labelled simulated."""
    name = "SIMULATED"

    def candles(self, symbol: str, timeframe: str, limit: int = 120) -> list[Candle]:
        seed = sum(map(ord, symbol.upper())) + sum(map(ord, timeframe))
        start = 100 + seed % 50
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        candles: list[Candle] = []
        for index in range(limit):
            trend = index * 0.08
            wave = math.sin((index + seed) / 6) * 1.4
            close = max(0.01, start + trend + wave)
            open_ = candles[-1].close if candles else close - 0.2
            spread = 0.45 + abs(math.sin(index)) * 0.35
            candles.append(Candle(now - timedelta(minutes=(limit - index) * 5), open_, max(open_, close) + spread, min(open_, close) - spread, close, 1000 + (index % 11) * 90))
        return candles


def sma(values: list[float], period: int) -> float:
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float:
    value = values[0]; alpha = 2 / (period + 1)
    for price in values[1:]: value = alpha * price + (1 - alpha) * value
    return value


def rsi(values: list[float], period: int = 14) -> float:
    changes = [values[index] - values[index - 1] for index in range(1, len(values))][-period:]
    gains = sum(max(change, 0) for change in changes) / period
    losses = sum(max(-change, 0) for change in changes) / period
    return 100 if losses == 0 else 100 - 100 / (1 + gains / losses)


def atr(candles: list[Candle], period: int = 14) -> float:
    ranges = [max(candle.high - candle.low, abs(candle.high - previous.close), abs(candle.low - previous.close)) for previous, candle in zip(candles, candles[1:])]
    return sum(ranges[-period:]) / period


def features(candles: list[Candle]) -> dict[str, float]:
    closes = [item.close for item in candles]
    fast, slow = ema(closes[-30:], 12), ema(closes[-60:], 26)
    volatility = atr(candles) / closes[-1]
    return {"close": closes[-1], "ema_fast": fast, "ema_slow": slow, "rsi": rsi(closes), "atr": atr(candles), "volatility": volatility, "volume_ratio": candles[-1].volume / sma([item.volume for item in candles], 20)}


def detect_regime(data: dict[str, float]) -> tuple[str, float, list[str]]:
    bullish = data["ema_fast"] > data["ema_slow"]
    if data["volatility"] > 0.025: return "HIGH_VOLATILITY", .65, ["elevated ATR"]
    if bullish and data["rsi"] > 55: return "TRENDING_BULLISH", .72, ["EMA alignment", "positive momentum"]
    if not bullish and data["rsi"] < 45: return "TRENDING_BEARISH", .72, ["EMA alignment", "negative momentum"]
    return "RANGE_BOUND", .55, ["mixed EMA and momentum"]


def make_decision(symbol: str, timeframe: str, candles: list[Candle], balance: float, rules: dict[str, float | int | bool]) -> Decision:
    data = features(candles); regime, regime_confidence, factors = detect_regime(data)
    direction = "BUY" if regime == "TRENDING_BULLISH" else "SELL" if regime == "TRENDING_BEARISH" else "HOLD"
    entry, unit_risk = data["close"], max(data["atr"] * 1.5, .01)
    stop = entry - unit_risk if direction == "BUY" else entry + unit_risk
    target = entry + unit_risk * 2 if direction == "BUY" else entry - unit_risk * 2
    risk_amount = balance * float(rules["max_risk_per_trade"])
    quantity = risk_amount / unit_risk if direction != "HOLD" else 0
    score = min(100, int(regime_confidence * 100 + (data["volume_ratio"] - 1) * 10))
    rejected: list[str] = []
    if rules.get("kill_switch"): rejected.append("paper trading kill switch is enabled")
    if direction == "HOLD": rejected.append("no strategy-regime compatibility")
    if regime_confidence < float(rules["min_confidence"]): rejected.append("confidence below minimum")
    if 2 < float(rules["min_risk_reward"]): rejected.append("risk/reward below minimum")
    final = direction if not rejected else "REJECTED"
    return Decision(str(uuid.uuid4()), symbol.upper(), timeframe, regime, "trend_following", direction, entry, stop, target, quantity, risk_amount, 2.0, score, regime_confidence, factors, [], rejected, final)


def backtest(symbol: str, candles: list[Candle], rules: dict[str, float | int | bool]) -> dict:
    """Walk-forward evaluation: every decision uses candles available before it."""
    balance, peak, trades, wins, pnl = 10000.0, 10000.0, 0, 0, 0.0
    for index in range(60, len(candles) - 1):
        decision = make_decision(symbol, "5m", candles[:index], balance, rules)
        if decision.final_decision == "REJECTED": continue
        next_close = candles[index].close
        result = (next_close - decision.entry) * decision.quantity if decision.direction == "BUY" else (decision.entry - next_close) * decision.quantity
        fee = decision.entry * decision.quantity * .0005
        result -= fee; balance += result; pnl += result; trades += 1; wins += result > 0; peak = max(peak, balance)
    return {"symbol": symbol, "mode": "BACKTEST", "trades": trades, "net_pnl": round(pnl, 2), "win_rate": round(wins / trades, 3) if trades else 0, "max_drawdown": round((peak - balance) / peak, 4) if peak else 0, "note": "Historical simulation only; not evidence of future performance."}
