from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AnalyzeRequest(BaseModel):
    contract_type: str = Field(..., min_length=1, max_length=64, description="Type of the contract (e.g. kira_sozlesmesi)")
    features: list[str] = Field(default_factory=list, max_length=200, description="Feature names present in this contract")
    # NOTE: pydantic v2 dict alanlarda `max_length` desteklemediği için kaldırıldı.
    # Bu alan main-server tarafından genelde boş ({}) gönderilir.
    fields: dict = Field(default_factory=dict, description="Extracted field values")
    completeness_score: Optional[float] = Field(None, ge=0, le=100)

    # ── Hafta 2 ──────────────────────────────────────────────────────────────
    # [{clause, reason, law_reference, necessity}]
    clause_data: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=200)
    optional_clauses_offered: int = Field(default=0, ge=0)
    optional_clauses_selected: int = Field(default=0, ge=0)


class FeatureRecommendation(BaseModel):
    feature_name: str
    usage_percentage: float
    count: int
    total: int
    message: str
    reason: str  # Makine tarafından okunabilir neden kodu (jüri: açıklanabilir AI)


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


# ── Hafta 2: Açıklama Desteği ────────────────────────────────────────────────

class ClauseUsageStat(BaseModel):
    """Bir sözleşme maddesinin kullanım istatistiği."""
    clause: str
    usage_percentage: float
    count: int
    total: int


class ExplanationSupportResponse(BaseModel):
    """
    GET /stats/{contract_type}/explanation-support endpoint yanıtı.
    UI ve ExplanationService'e istatistiksel destek verisi sağlar.
    """
    contract_type: str
    total_contracts: int
    avg_completeness: Optional[float]

    # Madde kullanım oranları (feature_counts'tan türetilir)
    clause_usage: List[ClauseUsageStat]

    # Opsiyonel madde seçim oranı (0.0–1.0); veri yoksa null
    optional_clause_selection_rate: Optional[float]

    # Onay tamamlanma oranı (0.0–1.0); veri yoksa null
    approval_completion_rate: Optional[float]
