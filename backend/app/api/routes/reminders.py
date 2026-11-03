from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.models import Reminder
from app.db.session import get_db
from app.schemas.reminder import (
    ReminderCreate,
    ReminderRead,
    ReminderStatus,
    ReminderUpdate,
)
from app.services import reminder_service

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    session: DbSession,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    status: ReminderStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Reminder]:
    return reminder_service.list_reminders(
        session,
        pet_id=pet_id,
        unlinked=unlinked,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(reminder_in: ReminderCreate, session: DbSession) -> Reminder:
    return reminder_service.create_reminder(session, reminder_in)


@router.get("/{reminder_id}", response_model=ReminderRead)
def get_reminder(reminder_id: UUID, session: DbSession) -> Reminder:
    return reminder_service.get_reminder_or_404(session, reminder_id)


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: UUID, reminder_in: ReminderUpdate, session: DbSession
) -> Reminder:
    return reminder_service.update_reminder(session, reminder_id, reminder_in)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(reminder_id: UUID, session: DbSession) -> Response:
    reminder_service.delete_reminder(session, reminder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
