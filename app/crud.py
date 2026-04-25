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
        # Hafta 2 alanları
        clause_data=req.clause_data,
        optional_clauses_offered=req.optional_clauses_offered,
        optional_clauses_selected=req.optional_clauses_selected,
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


def mark_latest_outcome(db: Session, contract_type: str, approved: bool) -> bool:
    """
    Verilen sözleşme tipi için en son işlemsiz kaydı onay/ret sonucuyla günceller.
    Kayıt bulunamazsa False döner (sessiz başarısızlık — fire-and-forget çağrısı için).
    """
    record = (
        db.query(ContractRecord)
        .filter(
            ContractRecord.contract_type == contract_type,
            ContractRecord.approval_completed.is_(None),
        )
        .order_by(ContractRecord.analyzed_at.desc())
        .first()
    )
    if record is None:
        return False
    record.approval_completed = approved
    db.commit()
    return True


def get_explanation_support(db: Session, contract_type: str) -> dict:
    """
    Açıklama desteği için zenginleştirilmiş istatistikler.
    Clause kullanım oranları, opsiyonel madde seçim oranı ve onay tamamlanma oranı.
    """
    records = get_records_by_type(db, contract_type)
    total = len(records)

    if total == 0:
        return {
            "total": 0,
            "avg_completeness": None,
            "feature_counts": {},
            "optional_clause_selection_rate": None,
            "approval_completion_rate": None,
        }

    feature_counts: dict[str, int] = {}
    completeness_values = []
    total_offered = 0
    total_selected = 0
    approval_count = 0
    approval_data_count = 0

    for record in records:
        for feature in (record.features or []):
            feature_counts[feature] = feature_counts.get(feature, 0) + 1

        if record.completeness_score is not None:
            completeness_values.append(record.completeness_score)

        if record.optional_clauses_offered is not None and record.optional_clauses_offered > 0:
            total_offered += record.optional_clauses_offered
            total_selected += (record.optional_clauses_selected or 0)

        if record.approval_completed is not None:
            approval_data_count += 1
            if record.approval_completed:
                approval_count += 1

    avg_completeness = (
        sum(completeness_values) / len(completeness_values)
        if completeness_values else None
    )
    optional_rate = (total_selected / total_offered) if total_offered > 0 else None
    approval_rate = (approval_count / approval_data_count) if approval_data_count > 0 else None

    return {
        "total": total,
        "avg_completeness": avg_completeness,
        "feature_counts": feature_counts,
        "optional_clause_selection_rate": optional_rate,
        "approval_completion_rate": approval_rate,
    }
