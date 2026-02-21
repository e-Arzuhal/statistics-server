from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AnalyzeRequest(BaseModel):
    contract_type: str = Field(..., description="Type of the contract (e.g. kira_sozlesmesi)")
    features: list[str] = Field(default=[], description="Feature names present in this contract")
    fields: dict = Field(default={}, description="Extracted field values")
    completeness_score: Optional[float] = Field(None, ge=0, le=100)


class FeatureRecommendation(BaseModel):
    feature_name: str
    usage_percentage: float
    count: int
    total: int
    message: str


class AnalyzeResponse(BaseModel):
    contract_type: str
    record_id: int
    recommendations: list[FeatureRecommendation]
    stats_summary: dict


class FeatureStat(BaseModel):
    feature_name: str
    count: int
    usage_percentage: float


class StatsResponse(BaseModel):
    contract_type: str
    total_contracts: int
    feature_stats: list[FeatureStat]
    avg_completeness: Optional[float]


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
