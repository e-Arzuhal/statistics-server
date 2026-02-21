from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db, create_tables
from .schemas import AnalyzeRequest, AnalyzeResponse, StatsResponse, HealthResponse, FeatureStat
from .crud import create_record, get_stats
from .services.recommendation import compute_recommendations

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contract feature usage statistics and recommendation service for e-Arzuhal",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()


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

    # Generate recommendations (exclude features already in this contract)
    recommendations = compute_recommendations(
        current_features=req.features,
        feature_counts=stats["feature_counts"],
        total=stats["total"],
    )

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
