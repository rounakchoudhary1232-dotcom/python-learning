"""Deterministic research stress harness built on the existing BacktestEngine."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from .backtesting import BacktestConfig, BacktestEngine
from .trading import Candle

@dataclass(frozen=True)
class StressScenario:
    name:str; symbol:str="STRESS"; timeframe:str="5m"; candles:list[Candle]=None; config:BacktestConfig=BacktestConfig(); expect_valid:bool=True; minimum_trades:int=0; minimum_rejections:int=0; minimum_drawdown:float=0.; minimum_execution_cost:float=0.; required_reason:str|None=None; required_quality_warning:str|None=None; required_exit_reason:str|None=None
@dataclass(frozen=True)
class StressResult:
    scenario_name:str; passed:bool; trade_count:int; rejected_trades:int; net_pnl:float; gross_pnl:float; execution_costs:float; max_drawdown:float; reasons:list[str]; data_quality:dict|None
    def payload(self)->dict:return asdict(self)
class StressTester:
    def __init__(self,engine:BacktestEngine|None=None):self.engine=engine or BacktestEngine()
    def run(self,scenario:StressScenario)->StressResult:
        if not scenario.name or not scenario.symbol or not scenario.timeframe or not scenario.candles:raise ValueError("stress scenario requires name, symbol, timeframe, and candles")
        result=self.engine.run(scenario.symbol,scenario.timeframe,scenario.candles,scenario.config)
        risk_rejections=[point["risk"]["reasons"] for point in result.strategy_research if "risk" in point and not point["risk"]["allowed"]]
        reasons=list(result.errors)+[reason for group in risk_rejections for reason in group]
        quality_warnings=[item["code"] for item in (result.data_quality or {}).get("warnings",[])]
        costs=round(sum(t.total_execution_cost for t in result.trades),2)
        passed=(result.valid==scenario.expect_valid and len(result.trades)>=scenario.minimum_trades and len(risk_rejections)>=scenario.minimum_rejections and result.metrics.get("max_drawdown",0)>=scenario.minimum_drawdown and costs>=scenario.minimum_execution_cost and (scenario.required_reason is None or scenario.required_reason in reasons) and (scenario.required_quality_warning is None or scenario.required_quality_warning in quality_warnings) and (scenario.required_exit_reason is None or any(t.exit_reason==scenario.required_exit_reason for t in result.trades)))
        return StressResult(scenario.name,passed,len(result.trades),len(risk_rejections),round(sum(t.net_pnl for t in result.trades),2),round(sum(t.gross_pnl for t in result.trades),2),costs,result.metrics.get("max_drawdown",0),reasons,result.data_quality)
