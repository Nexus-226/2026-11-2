from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import DEFAULT_USER_ID, Record, Reminder


def list_records(
    session: Session,
    *,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    record_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Record]:
    statement = select(Record).where(Record.user_id == DEFAULT_USER_ID)
    if pet_id is not None:
        statement = statement.where(Record.pet_id == str(pet_id))
    elif unlinked:
        statement = statement.where(Record.pet_id.is_(None))
    if record_type is not None:
        statement = statement.where(Record.record_type == record_type)
    if from_date is not None:
        statement = statement.where(Record.occurred_on >= from_date)
    if to_date is not None:
        statement = statement.where(Record.occurred_on <= to_date)
    statement = statement.order_by(
        Record.occurred_on.desc(), Record.created_at.desc(), Record.id.asc()
    )
    return list(session.scalars(statement))


def get_record(session: Session, record_id: UUID) -> Record | None:
    return session.scalar(
        select(Record).where(
            Record.id == str(record_id),
            Record.user_id == DEFAULT_USER_ID,
        )
    )


def create_record(
    session: Session,
    *,
    record_id: UUID,
    user_id: str,
    pet_id: str | None,
    record_type: str,
    occurred_on: date,
    name: str | None,
    weight_kg: Decimal | None,
    notes: str | None,
) -> Record:
    record = Record(
        id=str(record_id),
        user_id=user_id,
        pet_id=pet_id,
        record_type=record_type,
        occurred_on=occurred_on,
        name=name,
        weight_kg=weight_kg,
        notes=notes,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def update_record(
    session: Session, record: Record, values: dict[str, object]
) -> Record:
    for field, value in values.items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return record


def delete_record(session: Session, record: Record) -> None:
    session.execute(
        update(Reminder)
        .where(
            Reminder.user_id == record.user_id,
            Reminder.source_record_id == record.id,
        )
        .values(source_record_id=None)
    )
    session.delete(record)
    session.commit()


def has_records_for_pet(session: Session, pet_id: UUID) -> bool:
    return (
        session.scalar(
            select(Record.id)
            .where(
                Record.user_id == DEFAULT_USER_ID,
                Record.pet_id == str(pet_id),
            )
            .limit(1)
        )
        is not None
    )
