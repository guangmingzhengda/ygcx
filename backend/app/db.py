from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column(table: str, column: str, decl: str) -> None:
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        names = {row[1] for row in rows}
        if column not in names:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {decl}"))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_column("profiles", "expected_salary_min", "INTEGER DEFAULT 0")
    _ensure_column("profiles", "expected_salary_max", "INTEGER DEFAULT 0")
    _ensure_column("jobs", "salary_min", "INTEGER DEFAULT 0")
    _ensure_column("jobs", "salary_max", "INTEGER DEFAULT 0")
    _ensure_column("jobs", "salary_text", "VARCHAR(64) DEFAULT ''")
