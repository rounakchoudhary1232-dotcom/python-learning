"""Deterministic, research-only historical simulation with no broker access."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from statistics import median
import math
from .trading import Candle, analyze_market, validate_candles
from .strategies import StrategyEvaluator
from .decision_engine import DecisionConstraints, DecisionEngine
from .risk_engine import AccountRiskState, RiskLimits, assess
from .execution_costs import ExecutionCostConfig, ExecutionCostModel
from .data_quality import DataQualityConfig, validate_historical_data

def split_historical_candles(candles:list[Candle], split_ratio:float, minimum:int=2)->tuple[list[Candle],list[Candle]]:
    """Return chronological copies for future IS/OOS research; never mutates input."""
    if not 0 < split_ratio < 1: raise ValueError("split_ratio must be between 0 and 1")
    if len(candles)<minimum: raise ValueError("insufficient candles for historical split")
    boundary=int(len(candles)*split_ratio)
    if boundary==0 or boundary==len(candles): raise ValueError("split leaves an empty historical partition")
    return list(candles[:boundary]),list(candles[boundary:])
@dataclass(frozen=True)
class WalkForwardConfig:
    train_size:int; test_size:int; step_size:int
def walk_forward_windows(candles:list[Candle],config:WalkForwardConfig)->list[tuple[list[Candle],list[Candle]]]:
    if min(config.train_size,config.test_size,config.step_size)<=0:raise ValueError("walk-forward sizes must be positive")
    windows=[];start=0
    while start+config.train_size+config.test_size<=len(candles):
        windows.append((list(candles[start:start+config.train_size]),list(candles[start+config.train_size:start+config.train_size+config.test_size])));start+=config.step_size
    return windows

@dataclass(frozen=True)
class BacktestConfig:
    initial_balance: float = 10000.; fee_rate: float = 0.; slippage_rate: float = 0.; minimum_history: int = 20; split_ratio: float | None = None; execution_costs: ExecutionCostConfig = ExecutionCostConfig(); data_quality: DataQualityConfig = DataQualityConfig()
@dataclass(frozen=True)
class BacktestTrade:
    direction:str; entry_timestamp:str; entry:float; stop_loss:float; take_profit:float; quantity:float; exit_timestamp:str; exit_price:float; exit_reason:str; gross_pnl:float; fees:float; net_pnl:float; r_multiple:float; entry_reference_price:float|None=None; exit_reference_price:float|None=None; entry_fee:float=0.; exit_fee:float=0.; total_execution_cost:float=0.
@dataclass(frozen=True)
class EquityPoint:
    timestamp:str; balance:float; drawdown:float
@dataclass(frozen=True)
class BacktestResult:
    symbol:str; timeframe:str; valid:bool; errors:list[str]; trades:list[BacktestTrade]; equity_curve:list[EquityPoint]; metrics:dict; warnings:list[str]; strategy_research:list[dict]; strategy_statistics:dict; regime_statistics:dict; in_sample:dict|None=None; out_of_sample:dict|None=None; split_ratio:float|None=None; walk_forward_results:list[dict]|None=None; paper_only:bool=True; research_only:bool=True; data_quality:dict|None=None
    def payload(self)->dict:return asdict(self)

class BacktestEngine:
    """Signals at N close, enters only at N+1 open; both touched exits use SL first."""
    def __init__(self,evaluator:StrategyEvaluator|None=None,decision_engine:DecisionEngine|None=None): self.evaluator=evaluator or StrategyEvaluator();self.decision_engine=decision_engine or DecisionEngine(self.evaluator)
    def run(self,symbol:str,timeframe:str,candles:list[Candle],config:BacktestConfig=BacktestConfig())->BacktestResult:
        if config.split_ratio is not None:
            quality=validate_historical_data(candles,_quality_config(config))
            if not quality.valid:return _quality_failure(symbol,timeframe,quality)
            ins,oos=split_historical_candles(candles,config.split_ratio)
            base=BacktestConfig(config.initial_balance,config.fee_rate,config.slippage_rate,config.minimum_history,execution_costs=config.execution_costs,data_quality=config.data_quality)
            result=self.run(symbol,timeframe,ins,base)
            oos_result=self.run(symbol,timeframe,oos,base)
            return BacktestResult(symbol=result.symbol,timeframe=result.timeframe,valid=result.valid,errors=result.errors,trades=result.trades,equity_curve=result.equity_curve,metrics=result.metrics,warnings=result.warnings,strategy_research=result.strategy_research,strategy_statistics=result.strategy_statistics,regime_statistics=result.regime_statistics,in_sample=result.payload(),out_of_sample=oos_result.payload(),split_ratio=config.split_ratio,paper_only=result.paper_only,research_only=result.research_only,data_quality=quality.payload())
        quality=validate_historical_data(candles,_quality_config(config))
        if not quality.valid:return _quality_failure(symbol,timeframe,quality)
        balance,peak=config.initial_balance,config.initial_balance; trades=[]; curve=[]; research=[]
        # Pure deterministic research signal: previous close direction; no future values are read.
        for n in range(config.minimum_history,len(candles)-1):
            context=analyze_market(symbol,timeframe,candles[:n+1])
            signals=self.evaluator.evaluate(context)
            decision=self.decision_engine.decide(context,DecisionConstraints(.6,1.5),signals)
            research.append({"timestamp":candles[n].timestamp.isoformat(),"regime":context.regime["state"],"signals":[item.payload() for item in signals],"decision":decision.payload()})
            signal=decision.action
            if signal not in {"BUY","SELL"}: continue
            entry_candle=candles[n+1]; entry=entry_candle.open; risk=max(entry*.01,.01); stop=entry-risk if signal=="BUY" else entry+risk; target=entry+2*risk if signal=="BUY" else entry-2*risk; qty=(balance*.01)/risk
            assessment=assess(signal,entry,stop,target,None,AccountRiskState(balance,balance,trade_count_today=len(trades)),RiskLimits(.01,1.5,.03,5,.10))
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
            costs=ExecutionCostModel(_cost_config(config)).round_trip(signal,entry,exit_price,qty); gross=(costs.exit_price-costs.entry_price)*qty if signal=="BUY" else (costs.entry_price-costs.exit_price)*qty; fees=costs.entry_fee+costs.exit_fee; net=gross-fees; balance+=net; peak=max(peak,balance); trade=BacktestTrade(signal,entry_candle.timestamp.isoformat(),costs.entry_price,stop,target,qty,exit_candle.timestamp.isoformat(),costs.exit_price,reason,gross,fees,net,net/(risk*qty),entry,exit_price,costs.entry_fee,costs.exit_fee,costs.total_cost);trades.append(trade);research[-1]["closed_trade_index"]=len(trades)-1;curve.append(EquityPoint(exit_candle.timestamp.isoformat(),balance,(peak-balance)/peak))
        wins=[t.net_pnl for t in trades if t.net_pnl>0];losses=[t.net_pnl for t in trades if t.net_pnl<0]; gross_profit=sum(wins);gross_loss=abs(sum(losses));returns=[t.net_pnl/config.initial_balance for t in trades];streaks=_streaks(trades);maxdd=max((p.drawdown for p in curve),default=0);maxdd_absolute=_max_drawdown_absolute(config.initial_balance,curve);metrics={"total_trades":len(trades),"net_profit":round(balance-config.initial_balance,2),"final_balance":round(balance,2),"win_rate":round(len(wins)/len(trades),3) if trades else 0,"profit_factor":round(gross_profit/gross_loss,3) if gross_loss else 0,"expectancy":round(sum(t.net_pnl for t in trades)/len(trades),2) if trades else 0,"average_r":round(sum(t.r_multiple for t in trades)/len(trades),3) if trades else 0,"max_drawdown":maxdd,"max_drawdown_percent":maxdd,"max_drawdown_absolute":round(maxdd_absolute,2),"maximum_drawdown_duration":_drawdown_duration(curve),"average_trade_return":round(sum(returns)/len(returns),6) if returns else None,"median_trade_return":round(median(returns),6) if returns else None,"consecutive_wins":streaks[0],"consecutive_losses":streaks[1],"average_win":round(sum(wins)/len(wins),2) if wins else None,"average_loss":round(sum(losses)/len(losses),2) if losses else None,"largest_win":round(max(wins),2) if wins else None,"largest_loss":round(min(losses),2) if losses else None,"breakeven_trades":len(trades)-len(wins)-len(losses),"sharpe_like":_sharpe(returns)}
        warnings=[]
        if len(trades)<10:warnings.append("very few trades; research result is limited")
        if _cost_config(config)==ExecutionCostConfig():warnings.append("zero-cost simulation")
        if metrics["sharpe_like"] is None:warnings.append("risk-adjusted metric unavailable: insufficient or zero-variance returns")
        strategy_groups={};regime_groups={}
        for point in research:
            if "closed_trade_index" not in point:continue
            trade=trades[point["closed_trade_index"]]
            for name in point["decision"].get("selected_strategies",[]):strategy_groups.setdefault(name,[]).append(trade)
            regime_groups.setdefault(point["regime"],[]).append(trade)
        return BacktestResult(symbol,timeframe,True,[],trades,curve,metrics,warnings+[item["message"] for item in quality.warnings],research,{k:_statistics(v) for k,v in strategy_groups.items()},{k:_statistics(v) for k,v in regime_groups.items()},data_quality=quality.payload())

    def walk_forward(self,symbol:str,timeframe:str,candles:list[Candle],config:WalkForwardConfig,backtest_config:BacktestConfig=BacktestConfig())->list[dict]:
        windows=walk_forward_windows(candles,config)
        if not windows: return []
        return [{"window_index":i,"train_start":train[0].timestamp.isoformat(),"train_end":train[-1].timestamp.isoformat(),"test_start":test[0].timestamp.isoformat(),"test_end":test[-1].timestamp.isoformat(),"train_candle_count":len(train),"test_candle_count":len(test),"result":self.run(symbol,timeframe,test,backtest_config).payload()} for i,(train,test) in enumerate(windows)]

def _statistics(trades:list[BacktestTrade])->dict:
    wins=[t for t in trades if t.net_pnl>0];losses=[t for t in trades if t.net_pnl<0];gross_profit=sum(t.net_pnl for t in wins);gross_loss=abs(sum(t.net_pnl for t in losses));count=len(trades)
    return {"trade_count":count,"wins":len(wins),"losses":len(losses),"breakeven":count-len(wins)-len(losses),"net_profit":round(sum(t.net_pnl for t in trades),2),"win_rate":round(len(wins)/count,3) if count else 0,"gross_profit":round(gross_profit,2),"gross_loss":round(gross_loss,2),"profit_factor":round(gross_profit/gross_loss,3) if gross_loss else None,"expectancy":round(sum(t.net_pnl for t in trades)/count,2) if count else 0,"average_r":round(sum(t.r_multiple for t in trades)/count,3) if count else 0}
def _streaks(trades):
    bestw=bestl=current=0;kind=None
    for trade in trades:
        nextkind="w" if trade.net_pnl>0 else "l" if trade.net_pnl<0 else None
        current=current+1 if nextkind and nextkind==kind else 1 if nextkind else 0;kind=nextkind
        if kind=="w":bestw=max(bestw,current)
        if kind=="l":bestl=max(bestl,current)
    return bestw,bestl
def _drawdown_duration(curve):
    peak=0;run=best=0
    for point in curve:
        if point.balance>=peak:peak=point.balance;run=0
        else:run+=1;best=max(best,run)
    return best
def _max_drawdown_absolute(initial_balance,curve):
    peak=initial_balance;maximum=0.
    for point in curve:
        peak=max(peak,point.balance);maximum=max(maximum,peak-point.balance)
    return maximum
def _sharpe(values):
    if len(values)<2:return None
    mean=sum(values)/len(values);variance=sum((x-mean)**2 for x in values)/len(values)
    return round(mean/math.sqrt(variance),6) if variance>0 else None
def _cost_config(config):
    """Use the new model while honoring legacy fee/slippage config fields."""
    if config.execution_costs != ExecutionCostConfig(): return config.execution_costs
    return ExecutionCostConfig(config.fee_rate,config.slippage_rate*10_000)
def _quality_config(config):
    """BacktestConfig.minimum_history remains the public backtest history requirement."""
    return DataQualityConfig(minimum_history=config.minimum_history,expected_timeframe=config.data_quality.expected_timeframe,strict_gaps=config.data_quality.strict_gaps)
def _quality_failure(symbol,timeframe,quality):
    return BacktestResult(symbol,timeframe,False,[item["message"] for item in quality.errors],[],[],{},["historical input rejected"]+[item["message"] for item in quality.warnings],[],{}, {},data_quality=quality.payload())
