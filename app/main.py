import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from .config import get_settings
from .database import get_db, create_tables
from .schemas import (AnalyzeRequest, AnalyzeResponse, StatsResponse, HealthResponse,
                      FeatureStat, ExplanationSupportResponse, ClauseUsageStat)
from .crud import create_record, get_records_by_type, get_stats, get_explanation_support, mark_latest_outcome
from .services.recommendation import compute_recommendations, compute_jaccard_recommendations

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contract feature usage statistics and recommendation service for e-Arzuhal",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS — izin verilen origin'ler env'den okunur (default: main-server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Her isteği X-Request-ID ve süre ile loglar; response'a request-id ekler."""
    if request.url.path in ("/health", "/"):
        return await call_next(request)
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "http_request service=statistics method=%s path=%s status=%d ms=%d request_id=%s",
        request.method, request.url.path, response.status_code, elapsed_ms, request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Internal API key kontrolü. Debug dışı ortamlarda zorunludur."""
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    if not settings.internal_api_key:
        if settings.debug:
            return await call_next(request)
        return JSONResponse(status_code=503, content={"detail": "Server misconfigured: INTERNAL_API_KEY is required"})

    if request.headers.get("X-Internal-API-Key") != settings.internal_api_key:
        return JSONResponse(status_code=401, content={"detail": "Geçersiz veya eksik API anahtarı"})
    return await call_next(request)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health():
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        service=settings.app_name,
    )


@app.post("/contracts/analyze", response_model=AnalyzeResponse, tags=["Statistics"])
def analyze_contract(req: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Store a contract's feature set and return recommendations based on historical usage.
    Recommendations: features used in >= 30% of same-type contracts that are NOT in this contract.
    """
    # Persist this record
    record = create_record(db, req)

    # Compute statistics (after inserting, so current contract is included)
    stats = get_stats(db, req.contract_type)

    # Frequency-based recommendations
    freq_recs = compute_recommendations(
        current_features=req.features,
        feature_counts=stats["feature_counts"],
        total=stats["total"],
    )

    # Jaccard-weighted recommendations (benzer sözleşmelere ağırlık verir)
    all_records = get_records_by_type(db, req.contract_type)
    jaccard_recs = compute_jaccard_recommendations(
        current_features=req.features,
        all_records=[r.features for r in all_records if r.features],
    )

    # Birleştir: Jaccard önerilerini önceliklendir, geri kalan frequency önerilerini ekle
    seen: set[str] = {r.feature_name for r in jaccard_recs}
    combined = jaccard_recs + [r for r in freq_recs if r.feature_name not in seen]
    recommendations = combined[:10]

    return AnalyzeResponse(
        contract_type=req.contract_type,
        record_id=record.id,
        recommendations=recommendations,
        stats_summary={
            "total_contracts": stats["total"],
            "avg_completeness": stats["avg_completeness"],
        },
    )


@app.get("/stats/{contract_type}", response_model=StatsResponse, tags=["Statistics"])
def get_contract_stats(contract_type: str, db: Session = Depends(get_db)):
    """
    Get aggregated feature usage statistics for a specific contract type.
    """
    stats = get_stats(db, contract_type)

    feature_stats = [
        FeatureStat(
            feature_name=name,
            count=count,
            usage_percentage=round((count / stats["total"]) * 100, 1) if stats["total"] > 0 else 0.0,
        )
        for name, count in sorted(
            stats["feature_counts"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    return StatsResponse(
        contract_type=contract_type,
        total_contracts=stats["total"],
        feature_stats=feature_stats,
        avg_completeness=stats["avg_completeness"],
    )


@app.get("/stats/{contract_type}/explanation-support",
         response_model=ExplanationSupportResponse,
         tags=["Statistics"])
def get_explanation_support_stats(contract_type: str, db: Session = Depends(get_db)):
    """
    Madde açıklama sistemi için istatistiksel destek verisi.
    Clause kullanım oranları, opsiyonel madde seçim oranı ve onay tamamlanma oranını döner.
    UI ve ExplanationService tarafından kullanılır.
    """
    data = get_explanation_support(db, contract_type)
    total = data["total"]

    clause_usage = [
        ClauseUsageStat(
            clause=name,
            count=count,
            total=total,
            usage_percentage=round((count / total) * 100, 1) if total > 0 else 0.0,
        )
        for name, count in sorted(
            data["feature_counts"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    return ExplanationSupportResponse(
        contract_type=contract_type,
        total_contracts=total,
        avg_completeness=data["avg_completeness"],
        clause_usage=clause_usage,
        optional_clause_selection_rate=data["optional_clause_selection_rate"],
        approval_completion_rate=data["approval_completion_rate"],
    )


@app.post("/stats/{contract_type}/mark-outcome", status_code=204, tags=["Statistics"])
def mark_contract_outcome(
    contract_type: str,
    approved: bool = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """
    Sözleşme onay/ret sonucunu istatistiklere yansıtır.
    O tip için en son işlemsiz (approval_completed=NULL) kaydı günceller.
    main-server tarafından approve()/reject() akışında fire-and-forget olarak çağrılır.
    """
    mark_latest_outcome(db, contract_type, approved)
