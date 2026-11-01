"""SQLAlchemy engine, session factory and the FastAPI session dependency."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Yield a DB session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (simple alternative to migrations; see schema.sql too)."""
    from app.database import models  # noqa: F401  (registers the models)

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    from app.services.billing_service import backfill_barcodes
    with SessionLocal() as db:
        backfill_barcodes(db)
        from app.services.catalog_service import ensure_catalog
        ensure_catalog(db)
        from app.services import access_service, hospital_service, registry_service
        hospital_service.default_branch(db)
        hospital_service.get_profile(db)
        access_service.seed_access(db)
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_patients_uhid ON patients (uhid)"))   # an old database got the column without the unique rule
        registry_service.backfill_uhids(db)
        from app.services import encounter_service
        encounter_service.seed_rules(db)
        from app.services import grade_service
        grade_service.migrate(db)
        from app.services import diagnostic_service
        diagnostic_service.migrate(db)
        encounter_service.seed_templates(db)


def add_missing_columns(bind=None) -> None:
    """Tiny migration step: create_all() makes NEW tables but never adds columns to tables that already exist.
    So when a model gains a column, add it here with ALTER TABLE (works on SQLite and PostgreSQL).
    Only nullable columns are added, so existing rows stay valid."""
    target = bind or engine
    inspector = inspect(target)
    with target.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    column_type = column.type.compile(dialect=target.dialect)
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
