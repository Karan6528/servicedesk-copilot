"""Database: SQLite locally, PostgreSQL in Docker / Kubernetes / Azure."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso_utc(dt: datetime | None) -> str | None:
    """SQLite drops tzinfo; values are always stored in UTC, so re-attach it."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    message: Mapped[str] = mapped_column(Text)

    language: Mapped[str] = mapped_column(String(5))
    category: Mapped[str] = mapped_column(String(40), index=True)
    urgency: Mapped[str] = mapped_column(String(10), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    engine: Mapped[str] = mapped_column(String(20), default="rules")
    matched: Mapped[str] = mapped_column(Text, default="")
    suggested_reply: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    servicenow_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    power_automate_notified: Mapped[bool] = mapped_column(default=False)


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Columns added after the first release. create_all() only creates missing
# tables, so older databases get these columns added here.
_ADDED_COLUMNS = {"customer_phone": "VARCHAR(40)"}


def init_db() -> None:
    Base.metadata.create_all(engine)
    existing = {c["name"] for c in inspect(engine).get_columns("tickets")}
    with engine.begin() as conn:
        for name, sql_type in _ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {name} {sql_type}"))


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
