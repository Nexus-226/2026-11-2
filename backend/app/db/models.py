from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    species: Mapped[str] = mapped_column(String(10), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Record(Base):
    __tablename__ = "records"
    __table_args__ = (
        CheckConstraint(
            "record_type IN ('vaccine', 'deworming', 'bath', 'weight')",
            name="ck_records_record_type",
        ),
        CheckConstraint(
            "(record_type = 'weight' AND weight_kg IS NOT NULL "
            "AND weight_kg > 0 AND weight_kg <= 500) "
            "OR (record_type != 'weight' AND weight_kg IS NULL)",
            name="ck_records_weight_by_type",
        ),
        Index("ix_records_user_pet_occurred", "user_id", "pet_id", "occurred_on"),
        Index("ix_records_user_occurred", "user_id", "occurred_on"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    pet_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pets.id", ondelete="RESTRICT"), nullable=True
    )
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_reminders_status",
        ),
        Index("ix_reminders_user_pet_due", "user_id", "pet_id", "due_on"),
        Index("ix_reminders_user_due", "user_id", "due_on"),
        Index("ix_reminders_source_record", "source_record_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    pet_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pets.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default="pending"
    )
    source_record_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("records.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "sequence", name="uq_chat_messages_session_sequence"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    history_reliable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=false()
    )
    pet_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_calls: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
