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
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Instrument, MarketData


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = ""
    timeframe: str = ""


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
            candles.append(Candle(now - timedelta(minutes=(limit - index) * 5), open_, max(open_, close) + spread, min(open_, close) - spread, close, 1000 + (index % 11) * 90, symbol.upper(), timeframe))
        return candles


def validate_candles(candles: list[Candle], minimum: int = 20) -> tuple[bool, list[str]]:
    """Validate ordered OHLCV without silently accepting malformed market data."""
    errors: list[str] = []
    if len(candles) < minimum: errors.append(f"insufficient history: need {minimum} candles")
    timestamps: set[datetime] = set()
    previous: datetime | None = None
    for item in candles:
        values = (item.open, item.high, item.low, item.close, item.volume)
        if not all(math.isfinite(value) for value in values): errors.append("non-finite OHLCV value"); break
        if item.high < max(item.open, item.close, item.low) or item.low > min(item.open, item.close, item.high): errors.append("invalid OHLC range"); break
        if item.volume < 0: errors.append("negative volume"); break
        if item.timestamp in timestamps: errors.append("duplicate candle timestamp"); break
        if previous and item.timestamp <= previous: errors.append("out-of-order candle timestamps"); break
        timestamps.add(item.timestamp); previous = item.timestamp
    return not errors, errors


class CandleRepository:
    """SQLite persistence boundary for validated provider candles."""
    def __init__(self, db: Session): self.db = db

    def save(self, candles: list[Candle]) -> int:
        valid, errors = validate_candles(candles, minimum=1)
        if not valid: raise ValueError("; ".join(errors))
        saved = 0
        for candle in candles:
            if not candle.symbol or not candle.timeframe:
                raise ValueError("candles require symbol and timeframe")
            instrument = self._instrument(candle.symbol)
            timestamp = candle.timestamp.astimezone(UTC).replace(tzinfo=None)
            existing = self.db.scalar(select(MarketData.id).where(MarketData.instrument_id == instrument.id, MarketData.timeframe == candle.timeframe, MarketData.timestamp == timestamp))
            if existing is None:
                self.db.add(MarketData(instrument_id=instrument.id, timeframe=candle.timeframe, timestamp=timestamp, open=candle.open, high=candle.high, low=candle.low, close=candle.close, volume=candle.volume))
                saved += 1
        self.db.commit()
        return saved

    def recent(self, symbol: str, timeframe: str, limit: int = 120) -> list[Candle]:
        rows = self.db.execute(select(MarketData, Instrument.symbol).join(Instrument).where(Instrument.symbol == symbol.upper(), MarketData.timeframe == timeframe).order_by(MarketData.timestamp.desc()).limit(limit)).all()
        return [Candle(row.timestamp.replace(tzinfo=UTC), row.open, row.high, row.low, row.close, row.volume, name, timeframe) for row, name in reversed(rows)]

    def _instrument(self, symbol: str) -> Instrument:
        instrument = self.db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
        if instrument is None:
            instrument = Instrument(symbol=symbol.upper(), asset_class="SIMULATED")
            self.db.add(instrument); self.db.flush()
        return instrument


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    timestamp: datetime
    current_price: float
    timeframe: str
    trend: str
    momentum: str
    volume_state: str
    volatility: dict
    structure: dict
    support_resistance: dict
    breakout: dict
    reversal: dict
    regime: dict
    mtf_summary: str
    data_quality: dict
    evidence: list[str]

    def payload(self) -> dict: return asdict(self)


def swings(candles: list[Candle], lookback: int = 3) -> dict[str, list[dict]]:
    highs: list[dict] = []; lows: list[dict] = []
    for index in range(lookback, len(candles) - lookback):
        window = candles[index - lookback:index + lookback + 1]
        if candles[index].high == max(item.high for item in window): highs.append({"index": index, "price": candles[index].high, "timestamp": candles[index].timestamp})
        if candles[index].low == min(item.low for item in window): lows.append({"index": index, "price": candles[index].low, "timestamp": candles[index].timestamp})
    return {"highs": highs[-6:], "lows": lows[-6:]}


def market_structure(candles: list[Candle], lookback: int = 3) -> dict:
    points = swings(candles, lookback); highs, lows = points["highs"], points["lows"]
    labels: list[str] = []
    if len(highs) >= 2: labels.append("HH" if highs[-1]["price"] > highs[-2]["price"] else "LH")
    if len(lows) >= 2: labels.append("HL" if lows[-1]["price"] > lows[-2]["price"] else "LL")
    state = "BULLISH" if {"HH", "HL"}.issubset(labels) else "BEARISH" if {"LH", "LL"}.issubset(labels) else "RANGING"
    close = candles[-1].close
    bos = "BULLISH_BOS" if highs and close > highs[-1]["price"] else "BEARISH_BOS" if lows and close < lows[-1]["price"] else "NONE"
    previous = "BULLISH" if len(labels) >= 2 and {"HH", "HL"}.issubset(labels[:-1]) else "BEARISH" if len(labels) >= 2 and {"LH", "LL"}.issubset(labels[:-1]) else "UNKNOWN"
    choch = "BULLISH_CHOCH" if previous == "BEARISH" and bos == "BULLISH_BOS" else "BEARISH_CHOCH" if previous == "BULLISH" and bos == "BEARISH_BOS" else "NONE"
    return {"state": state, "labels": labels, "swing_highs": highs, "swing_lows": lows, "bos": bos, "choch": choch, "strength": min(1.0, (len(highs) + len(lows)) / 8)}


def support_resistance(candles: list[Candle], structure: dict, tolerance: float = .006) -> dict:
    price = candles[-1].close; levels = [item["price"] for item in structure["swing_highs"] + structure["swing_lows"]]
    support = max((level for level in levels if level <= price), default=None); resistance = min((level for level in levels if level >= price), default=None)
    distance = lambda level: round(abs(price - level) / price, 5) if level else None
    return {"support": support, "resistance": resistance, "support_distance": distance(support), "resistance_distance": distance(resistance), "near_support": bool(support and distance(support) <= tolerance), "near_resistance": bool(resistance and distance(resistance) <= tolerance)}


def volatility_analysis(candles: list[Candle]) -> dict:
    closes = [item.close for item in candles]; current_atr = atr(candles); atr_pct = current_atr / closes[-1]
    returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))][-20:]
    rolling = math.sqrt(sum(item * item for item in returns) / len(returns)) if returns else 0.0
    state = "EXTREME" if atr_pct > .04 else "HIGH" if atr_pct > .025 else "LOW" if atr_pct < .008 else "NORMAL"
    return {"atr": current_atr, "atr_percent": atr_pct, "rolling_volatility": rolling, "state": state}


def breakout_detection(candles: list[Candle], levels: dict, volatility: dict) -> dict:
    close, volume = candles[-1].close, candles[-1].volume; average_volume = sma([item.volume for item in candles], min(20, len(candles)))
    resistance, support = levels["resistance"], levels["support"]
    if resistance and close > resistance:
        strength = (close - resistance) / max(volatility["atr"], .01); return {"state": "BULLISH_BREAKOUT" if strength >= .5 and volume >= average_volume else "WEAK_BULLISH_BREAKOUT", "strength": strength}
    if support and close < support:
        strength = (support - close) / max(volatility["atr"], .01); return {"state": "BEARISH_BREAKOUT" if strength >= .5 and volume >= average_volume else "WEAK_BEARISH_BREAKOUT", "strength": strength}
    return {"state": "NONE", "strength": 0.0}


def reversal_detection(data: dict[str, float], structure: dict, levels: dict, volatility: dict) -> dict:
    bullish = structure["choch"] == "BULLISH_CHOCH" or (levels["near_support"] and data["rsi"] < 35)
    bearish = structure["choch"] == "BEARISH_CHOCH" or (levels["near_resistance"] and data["rsi"] > 65)
    state = "BULLISH_EVIDENCE" if bullish and volatility["state"] != "EXTREME" else "BEARISH_EVIDENCE" if bearish and volatility["state"] != "EXTREME" else "NONE"
    return {"state": state, "evidence": [structure["choch"], "support/resistance interaction" if bullish or bearish else "no confluence"]}


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


def analyze_market(symbol: str, timeframe: str, candles: list[Candle], lower: list[Candle] | None = None, higher: list[Candle] | None = None) -> MarketContext:
    valid, errors = validate_candles(candles)
    if not valid:
        return MarketContext(symbol.upper(), candles[-1].timestamp if candles else datetime.now(UTC), candles[-1].close if candles else 0.0, timeframe, "UNCLEAR", "UNCLEAR", "UNKNOWN", {}, {}, {}, {"state": "NONE", "strength": 0.0}, {"state": "NONE", "evidence": errors}, {"state": "UNCLEAR", "confidence": 0.0, "evidence": errors}, "INSUFFICIENT_DATA", {"valid": False, "errors": errors}, errors)
    data = features(candles); structure = market_structure(candles); volatility = volatility_analysis(candles); levels = support_resistance(candles, structure); breakout = breakout_detection(candles, levels, volatility); reversal = reversal_detection(data, structure, levels, volatility)
    trend = "BULLISH" if data["ema_fast"] > data["ema_slow"] else "BEARISH"
    momentum = "BULLISH" if data["rsi"] > 55 else "BEARISH" if data["rsi"] < 45 else "NEUTRAL"
    volume_state = "EXPANDED" if data["volume_ratio"] >= 1.2 else "QUIET" if data["volume_ratio"] <= .8 else "NORMAL"
    if volatility["state"] in {"HIGH", "EXTREME"}: regime_name = "HIGH_VOLATILITY"
    elif volatility["state"] == "LOW": regime_name = "LOW_VOLATILITY"
    elif trend == "BULLISH" and structure["state"] == "BULLISH" and momentum == "BULLISH": regime_name = "TRENDING_BULL"
    elif trend == "BEARISH" and structure["state"] == "BEARISH" and momentum == "BEARISH": regime_name = "TRENDING_BEAR"
    elif structure["state"] == "RANGING": regime_name = "RANGE"
    else: regime_name = "UNCLEAR"
    contexts = [(trend, structure["state"])]
    for series in (higher, lower):
        if series and validate_candles(series)[0]:
            extra = features(series); contexts.append(("BULLISH" if extra["ema_fast"] > extra["ema_slow"] else "BEARISH", market_structure(series)["state"]))
    directions = [item[0] for item in contexts]
    mtf = "ALIGNED_BULLISH" if all(item == "BULLISH" for item in directions) else "ALIGNED_BEARISH" if all(item == "BEARISH" for item in directions) else "MIXED"
    evidence = [f"EMA trend: {trend}", f"RSI momentum: {momentum}", f"structure: {structure['state']}", f"volatility: {volatility['state']}"]
    return MarketContext(symbol.upper(), candles[-1].timestamp, data["close"], timeframe, trend, momentum, volume_state, volatility, structure, levels, breakout, reversal, {"state": regime_name, "confidence": round((structure["strength"] + (1 if momentum == trend else .5)) / 2, 2), "evidence": evidence}, mtf, {"valid": True, "errors": []}, evidence)


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
