"""Deterministic OHLCV quality validation for historical research input."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
import math
from .trading import Candle

_INTERVALS={"1m":60,"5m":300,"15m":900,"1h":3600,"1d":86400}
@dataclass(frozen=True)
class DataQualityConfig:
    minimum_history:int=0; expected_timeframe:str|None=None; strict_gaps:bool=False
@dataclass(frozen=True)
class DataQualityReport:
    valid:bool; errors:list[dict]; warnings:list[dict]; checked_candles:int; detected_duplicates:int; detected_ordering_issues:int; detected_gaps:int; detected_invalid_ohlc:int; detected_invalid_numeric_values:int; detected_non_positive_values:int; timeframe:str|None
    def payload(self)->dict:return asdict(self)
def validate_historical_data(candles:list[Candle],config:DataQualityConfig=DataQualityConfig())->DataQualityReport:
    errors=[];warnings=[];duplicates=ordering=gaps=ohlc=numeric=positive=0;previous=None;seen=set();interval=_INTERVALS.get(config.expected_timeframe or "")
    if not candles:errors.append(_issue("empty_data",None,None,"no historical candles supplied"))
    if len(candles)<config.minimum_history:errors.append(_issue("minimum_history",None,None,"insufficient historical candles"))
    for index,candle in enumerate(candles):
        timestamp=getattr(candle,"timestamp",None);stamp=timestamp.isoformat() if isinstance(timestamp,datetime) else None
        if not isinstance(timestamp,datetime):errors.append(_issue("invalid_timestamp",index,stamp,"timestamp is missing or invalid"));continue
        if timestamp in seen:duplicates+=1;errors.append(_issue("duplicate_timestamp",index,stamp,"duplicate timestamp"))
        if previous is not None and timestamp<=previous:ordering+=1;errors.append(_issue("ordering",index,stamp,"timestamps are not strictly ordered"))
        if previous is not None and interval:
            seconds=(timestamp-previous).total_seconds()
            if seconds!=interval:
                gaps+=1;target=errors if config.strict_gaps else warnings;target.append(_issue("timeframe_gap",index,stamp,"timestamp interval differs from expected timeframe"))
        seen.add(timestamp);previous=timestamp
        values=[getattr(candle,name,None) for name in ("open","high","low","close","volume")]
        if not all(isinstance(value,(int,float)) and math.isfinite(value) for value in values):numeric+=1;errors.append(_issue("invalid_numeric",index,stamp,"OHLCV values must be finite numbers"));continue
        open_,high,low,close,volume=values
        if any(value<=0 for value in (open_,high,low,close)):positive+=1;errors.append(_issue("non_positive_price",index,stamp,"prices must be strictly positive"))
        if volume<0:errors.append(_issue("negative_volume",index,stamp,"volume cannot be negative"))
        elif volume==0:warnings.append(_issue("zero_volume",index,stamp,"zero volume candle"))
        if high<max(open_,close,low) or low>min(open_,close,high):ohlc+=1;errors.append(_issue("invalid_ohlc",index,stamp,"invalid OHLC relationship"))
    return DataQualityReport(not errors,errors,warnings,len(candles),duplicates,ordering,gaps,ohlc,numeric,positive,config.expected_timeframe)
def _issue(code,index,timestamp,message):return {"code":code,"index":index,"timestamp":timestamp,"message":message}
