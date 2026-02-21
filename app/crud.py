from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import ContractRecord
from .schemas import AnalyzeRequest


def create_record(db: Session, req: AnalyzeRequest) -> ContractRecord:
    record = ContractRecord(
        contract_type=req.contract_type,
        features=req.features,
        fields=req.fields,
        completeness_score=req.completeness_score,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_records_by_type(db: Session, contract_type: str) -> list[ContractRecord]:
    return db.query(ContractRecord).filter(
        ContractRecord.contract_type == contract_type
    ).all()


def get_stats(db: Session, contract_type: str) -> dict:
    records = get_records_by_type(db, contract_type)
    total = len(records)
    if total == 0:
        return {"total": 0, "feature_counts": {}, "avg_completeness": None}

    feature_counts: dict[str, int] = {}
    completeness_values = []

    for record in records:
        for feature in (record.features or []):
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
        if record.completeness_score is not None:
            completeness_values.append(record.completeness_score)

    avg_completeness = (
        sum(completeness_values) / len(completeness_values)
        if completeness_values else None
    )

    return {
        "total": total,
        "feature_counts": feature_counts,
        "avg_completeness": avg_completeness,
    }
