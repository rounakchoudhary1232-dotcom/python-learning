"""Deterministic, research-only historical simulation with no broker access."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from .trading import Candle, analyze_market, validate_candles
from .strategies import StrategyEvaluator
from .decision_engine import DecisionConstraints, DecisionEngine
from .risk_engine import AccountRiskState, RiskLimits, assess

@dataclass(frozen=True)
class BacktestConfig:
    initial_balance: float = 10000.; fee_rate: float = 0.; slippage_rate: float = 0.; minimum_history: int = 20
@dataclass(frozen=True)
class BacktestTrade:
    direction:str; entry_timestamp:str; entry:float; stop_loss:float; take_profit:float; quantity:float; exit_timestamp:str; exit_price:float; exit_reason:str; gross_pnl:float; fees:float; net_pnl:float; r_multiple:float
@dataclass(frozen=True)
class EquityPoint:
    timestamp:str; balance:float; drawdown:float
@dataclass(frozen=True)
class BacktestResult:
    symbol:str; timeframe:str; valid:bool; errors:list[str]; trades:list[BacktestTrade]; equity_curve:list[EquityPoint]; metrics:dict; warnings:list[str]; strategy_research:list[dict]; paper_only:bool=True; research_only:bool=True
    def payload(self)->dict:return asdict(self)

class BacktestEngine:
    """Signals at N close, enters only at N+1 open; both touched exits use SL first."""
    def __init__(self,evaluator:StrategyEvaluator|None=None,decision_engine:DecisionEngine|None=None): self.evaluator=evaluator or StrategyEvaluator();self.decision_engine=decision_engine or DecisionEngine(self.evaluator)
    def run(self,symbol:str,timeframe:str,candles:list[Candle],config:BacktestConfig=BacktestConfig())->BacktestResult:
        valid,errors=validate_candles(candles,config.minimum_history)
        if not valid:return BacktestResult(symbol,timeframe,False,errors,[],[],{},["historical input rejected"],[])
        balance,peak=config.initial_balance,config.initial_balance; trades=[]; curve=[]; research=[]
        # Pure deterministic research signal: previous close direction; no future values are read.
        for n in range(config.minimum_history,len(candles)-1):
            context=analyze_market(symbol,timeframe,candles[:n+1])
            signals=self.evaluator.evaluate(context)
            decision=self.decision_engine.decide(context,DecisionConstraints(.6,1.5),signals)
            research.append({"timestamp":candles[n].timestamp.isoformat(),"regime":context.regime["state"],"signals":[item.payload() for item in signals],"decision":decision.payload()})
            signal=decision.action
            if signal not in {"BUY","SELL"}: continue
            entry_candle=candles[n+1]; entry=entry_candle.open*(1+config.slippage_rate if signal=="BUY" else 1-config.slippage_rate); risk=max(entry*.01,.01); stop=entry-risk if signal=="BUY" else entry+risk; target=entry+2*risk if signal=="BUY" else entry-2*risk; qty=(balance*.01)/risk
            assessment=assess(signal,entry,stop,target,context.timestamp,AccountRiskState(balance,balance,trade_count_today=len(trades)),RiskLimits(.01,1.5,.03,5,.10))
            research[-1]["risk"]=assessment.payload()
            if not assessment.allowed: continue
            qty=assessment.calculated_position_size
            exit_candle=entry_candle; exit_price=None; reason=None
            for candle in candles[n+1:]:
                # Conservative ordering: SL is checked before TP when both occur in one candle.
                if signal=="BUY" and candle.low<=stop: exit_price,reason=stop,"EXIT_SL";exit_candle=candle;break
                if signal=="BUY" and candle.high>=target: exit_price,reason=target,"EXIT_TP";exit_candle=candle;break
                if signal=="SELL" and candle.high>=stop: exit_price,reason=stop,"EXIT_SL";exit_candle=candle;break
                if signal=="SELL" and candle.low<=target: exit_price,reason=target,"EXIT_TP";exit_candle=candle;break
            if exit_price is None: continue
            gross=(exit_price-entry)*qty if signal=="BUY" else (entry-exit_price)*qty; fees=(entry+exit_price)*qty*config.fee_rate; net=gross-fees; balance+=net; peak=max(peak,balance); trades.append(BacktestTrade(signal,entry_candle.timestamp.isoformat(),entry,stop,target,qty,exit_candle.timestamp.isoformat(),exit_price,reason,gross,fees,net,net/(risk*qty)));curve.append(EquityPoint(exit_candle.timestamp.isoformat(),balance,(peak-balance)/peak))
        wins=[t.net_pnl for t in trades if t.net_pnl>0];losses=[t.net_pnl for t in trades if t.net_pnl<0]; gross_profit=sum(wins);gross_loss=abs(sum(losses));metrics={"total_trades":len(trades),"net_profit":round(balance-config.initial_balance,2),"final_balance":round(balance,2),"win_rate":round(len(wins)/len(trades),3) if trades else 0,"profit_factor":round(gross_profit/gross_loss,3) if gross_loss else 0,"expectancy":round(sum(t.net_pnl for t in trades)/len(trades),2) if trades else 0,"average_r":round(sum(t.r_multiple for t in trades)/len(trades),3) if trades else 0,"max_drawdown":max((p.drawdown for p in curve),default=0)}
        warnings=[]
        if len(trades)<10:warnings.append("very few trades; research result is limited")
        if config.fee_rate==0 and config.slippage_rate==0:warnings.append("zero-cost simulation")
        return BacktestResult(symbol,timeframe,True,[],trades,curve,metrics,warnings,research)
