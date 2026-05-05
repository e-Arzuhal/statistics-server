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


def _repair_sqlite_autoincrement() -> None:
    """
    SQLite, BigInteger PRIMARY KEY tanımıyla AUTOINCREMENT yapmaz — yalnızca
    INTEGER PRIMARY KEY (rowid alias) auto-increment olur. Bu kod, daha eski
    bir şema sürümünden gelip `contract_records.id` BIGINT olarak yaratılmış
    DB'lerde INSERT'in "NOT NULL constraint failed: contract_records.id"
    hatası vermesini önlemek için tabloyu yeniden oluşturur.

    Yalnızca SQLite'da çalışır ve sadece tablo zaten varsa devreye girer.
    `with_variant(Integer, "sqlite")` koyduktan sonra create_tables ile
    yaratılan yeni DB'ler doğrudan INTEGER alır; bu fonksiyon eski DB'leri
    yamar.
    """
    if not str(engine.url).startswith("sqlite"):
        return
    inspector = inspect(engine)
    if not inspector.has_table("contract_records"):
        return
    cols = {c["name"]: c for c in inspector.get_columns("contract_records")}
    id_col = cols.get("id")
    if id_col is None:
        return
    # SQLAlchemy SQLite reflection genellikle BIGINT'i "BIGINT" olarak,
    # INTEGER'ı "INTEGER" olarak verir. Sadece INTEGER ise rowid alias
    # olarak çalışır ve auto-increment garantilenir.
    type_str = str(id_col.get("type", "")).upper()
    if "INTEGER" in type_str and "BIGINT" not in type_str:
        return
    logger.warning(
        "contract_records.id is %s (expected INTEGER for SQLite autoincrement); "
        "rebuilding table to fix INSERT failures",
        type_str,
    )
    try:
        with engine.begin() as conn:
            existing_cols = [c["name"] for c in inspector.get_columns("contract_records")]
            col_list = ", ".join(existing_cols)
            conn.execute(text("ALTER TABLE contract_records RENAME TO contract_records__old"))
            # Yeni tabloyu (Integer id'li) Base.metadata üzerinden oluştur
            Base.metadata.tables["contract_records"].create(bind=conn)
            conn.execute(text(
                f"INSERT INTO contract_records ({col_list}) "
                f"SELECT {col_list} FROM contract_records__old"
            ))
            conn.execute(text("DROP TABLE contract_records__old"))
        logger.info("contract_records table rebuilt with INTEGER PRIMARY KEY")
    except Exception as e:
        logger.error("Failed to repair contract_records.id type: %s", e)


def create_tables():
    Base.metadata.create_all(bind=engine)
    _apply_runtime_migrations()
    _repair_sqlite_autoincrement()
