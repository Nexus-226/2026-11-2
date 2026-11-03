from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DEFAULT_USER_ID, Reminder


def list_reminders(
    session: Session,
    *,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Reminder]:
    statement = select(Reminder).where(Reminder.user_id == DEFAULT_USER_ID)
    if pet_id is not None:
        statement = statement.where(Reminder.pet_id == str(pet_id))
    elif unlinked:
        statement = statement.where(Reminder.pet_id.is_(None))
    if status is not None:
        statement = statement.where(Reminder.status == status)
    if from_date is not None:
        statement = statement.where(Reminder.due_on >= from_date)
    if to_date is not None:
        statement = statement.where(Reminder.due_on <= to_date)
    statement = statement.order_by(
        Reminder.due_on.asc(), Reminder.created_at.asc(), Reminder.id.asc()
    )
    return list(session.scalars(statement))


def get_reminder(session: Session, reminder_id: UUID) -> Reminder | None:
    return session.scalar(
        select(Reminder).where(
            Reminder.id == str(reminder_id),
            Reminder.user_id == DEFAULT_USER_ID,
        )
    )


def create_reminder(
    session: Session,
    *,
    reminder_id: UUID,
    user_id: str,
    pet_id: str | None,
    title: str,
    due_on: date,
    source_record_id: str | None,
) -> Reminder:
    reminder = Reminder(
        id=str(reminder_id),
        user_id=user_id,
        pet_id=pet_id,
        title=title,
        due_on=due_on,
        status="pending",
        source_record_id=source_record_id,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def update_reminder(
    session: Session, reminder: Reminder, values: dict[str, object]
) -> Reminder:
    for field, value in values.items():
        setattr(reminder, field, value)
    session.commit()
    session.refresh(reminder)
    return reminder


def delete_reminder(session: Session, reminder: Reminder) -> None:
    session.delete(reminder)
    session.commit()


def has_reminders_for_pet(session: Session, pet_id: UUID) -> bool:
    return (
        session.scalar(
            select(Reminder.id)
            .where(
                Reminder.user_id == DEFAULT_USER_ID,
                Reminder.pet_id == str(pet_id),
            )
            .limit(1)
        )
        is not None
    )


def has_reminders_for_source_record(session: Session, record_id: UUID) -> bool:
    return (
        session.scalar(
            select(Reminder.id)
            .where(
                Reminder.user_id == DEFAULT_USER_ID,
                Reminder.source_record_id == str(record_id),
            )
            .limit(1)
        )
        is not None
    )
