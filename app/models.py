from sqlalchemy import Column, BigInteger, String, Float, JSON, DateTime, func
from .database import Base


class ContractRecord(Base):
    __tablename__ = "contract_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_type = Column(String(100), nullable=False, index=True)
    features = Column(JSON, nullable=False, default=list)   # list of feature names present
    fields = Column(JSON, nullable=False, default=dict)     # extracted field key-value pairs
    completeness_score = Column(Float, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
