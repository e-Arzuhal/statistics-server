import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Hafta 2 alanları eski DB dosyalarında bulunmadığı için her açılışta
# güvenli ALTER TABLE ile şemayı senkronlar. Alembic yerine kullanılan
# hafif yaklaşım — yalnızca yeni kolon ekleme desteklenir.
_RUNTIME_MIGRATIONS = {
    "contract_records": [
        ("clause_data", "JSON"),
        ("optional_clauses_offered", "INTEGER DEFAULT 0"),
        ("optional_clauses_selected", "INTEGER DEFAULT 0"),
        ("approval_completed", "BOOLEAN"),
    ],
}


def _apply_runtime_migrations() -> None:
    inspector = inspect(engine)
    added: list[str] = []
    for table, columns in _RUNTIME_MIGRATIONS.items():
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns:
            if name in existing:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                added.append(f"{table}.{name}")
                logger.info("Migrated %s: added column %s", table, name)
            except Exception as e:
                logger.warning("Migration skipped for %s.%s: %s", table, name, e)
    if added:
        logger.info("Runtime migrations applied: %s", ", ".join(added))
    else:
        logger.info("Runtime migrations: schema is up to date")


def create_tables():
    Base.metadata.create_all(bind=engine)
    _apply_runtime_migrations()
