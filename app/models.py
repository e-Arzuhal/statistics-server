from sqlalchemy import Column, BigInteger, String, Float, JSON, DateTime, Integer, Boolean, func
from .database import Base


class ContractRecord(Base):
    __tablename__ = "contract_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_type = Column(String(100), nullable=False, index=True)
    features = Column(JSON, nullable=False, default=list)   # list of feature names present
    fields = Column(JSON, nullable=False, default=dict)     # extracted field key-value pairs
    completeness_score = Column(Float, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    # ── Hafta 2: Açıklama & İstatistik Zenginleştirme ────────────────────────
    # Her madde için {clause, reason, law_reference, necessity} listesi
    clause_data = Column(JSON, nullable=True)

    # Kullanıcıya sunulan opsiyonel madde sayısı
    optional_clauses_offered = Column(Integer, nullable=True, default=0)
    # Kullanıcının seçtiği opsiyonel madde sayısı
    optional_clauses_selected = Column(Integer, nullable=True, default=0)

    # Onay tamamlandı mı? (sözleşme COMPLETED durumuna geçtiğinde True)
    approval_completed = Column(Boolean, nullable=True)
