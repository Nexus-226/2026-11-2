from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Reminder
from app.db.repositories import pets as pet_repository
from app.db.repositories import records as record_repository
from app.db.repositories import reminders as reminder_repository
from app.db.repositories.pets import get_local_user
from app.schemas.reminder import (
    ReminderCreate,
    ReminderRead,
    ReminderStatus,
    ReminderUpdate,
)

REMINDER_STATUSES = frozenset({"pending", "completed", "cancelled"})


def _http_error(
    status_code: int, code: str, message: str, *, retryable: bool = False
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
    )


def _validate_references(
    session: Session,
    *,
    pet_id: UUID | None,
    source_record_id: UUID | None,
) -> tuple[str | None, str | None]:
    if pet_id is not None and pet_repository.get_pet(session, pet_id) is None:
        raise _http_error(404, "PET_NOT_FOUND", "未找到宠物")

    pet_id_value = str(pet_id) if pet_id is not None else None
    source_record_id_value = (
        str(source_record_id) if source_record_id is not None else None
    )
    if source_record_id is not None:
        source_record = record_repository.get_record(session, source_record_id)
        if source_record is None:
            raise _http_error(404, "RECORD_NOT_FOUND", "未找到来源记录")
        if source_record.pet_id != pet_id_value:
            raise _http_error(
                422,
                "VALIDATION_ERROR",
                "提醒与来源记录必须关联同一只宠物",
            )
    return pet_id_value, source_record_id_value


def list_reminders(
    session: Session,
    *,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    status: ReminderStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Reminder]:
    if unlinked and pet_id is not None:
        raise _http_error(400, "BAD_REQUEST", "unlinked 与 pet_id 不能同时使用")
    if status is not None and status not in REMINDER_STATUSES:
        raise _http_error(422, "VALIDATION_ERROR", "提醒状态无效")
    if pet_id is not None and pet_repository.get_pet(session, pet_id) is None:
        raise _http_error(404, "PET_NOT_FOUND", "未找到宠物")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise _http_error(400, "BAD_REQUEST", "开始日期不能晚于结束日期")
    return reminder_repository.list_reminders(
        session,
        pet_id=pet_id,
        unlinked=unlinked,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )


def get_reminder_or_404(session: Session, reminder_id: UUID) -> Reminder:
    reminder = reminder_repository.get_reminder(session, reminder_id)
    if reminder is None:
        raise _http_error(404, "REMINDER_NOT_FOUND", "未找到提醒")
    return reminder


def create_reminder(session: Session, values: ReminderCreate) -> Reminder:
    pet_id, source_record_id = _validate_references(
        session,
        pet_id=values.pet_id,
        source_record_id=values.source_record_id,
    )
    user = get_local_user(session)
    return reminder_repository.create_reminder(
        session,
        reminder_id=uuid4(),
        user_id=user.id,
        pet_id=pet_id,
        title=values.title,
        due_on=values.due_on,
        source_record_id=source_record_id,
    )


def update_reminder(
    session: Session, reminder_id: UUID, values: ReminderUpdate
) -> Reminder:
    reminder = get_reminder_or_404(session, reminder_id)
    update_values = values.model_dump(exclude_unset=True)

    merged_values: dict[str, object] = {
        "pet_id": reminder.pet_id,
        "title": reminder.title,
        "due_on": reminder.due_on,
        "source_record_id": reminder.source_record_id,
    }
    merged_values.update(
        {key: value for key, value in update_values.items() if key != "status"}
    )
    try:
        validated = ReminderCreate.model_validate(merged_values)
    except ValidationError as exc:
        raise _http_error(
            422, "VALIDATION_ERROR", "更新后的提醒字段不符合要求"
        ) from exc

    new_status = update_values.get("status", reminder.status)
    if new_status != reminder.status and reminder.status != "pending":
        raise _http_error(
            422,
            "VALIDATION_ERROR",
            "已完成或已取消的提醒不能重新开启",
        )

    pet_id, source_record_id = _validate_references(
        session,
        pet_id=validated.pet_id,
        source_record_id=validated.source_record_id,
    )
    new_values: dict[str, object] = {
        "pet_id": pet_id,
        "title": validated.title,
        "due_on": validated.due_on,
        "source_record_id": source_record_id,
        "status": new_status,
    }
    if all(getattr(reminder, key) == value for key, value in new_values.items()):
        return reminder
    return reminder_repository.update_reminder(session, reminder, new_values)


def delete_reminder(session: Session, reminder_id: UUID) -> None:
    reminder_repository.delete_reminder(
        session, get_reminder_or_404(session, reminder_id)
    )


def ensure_pet_can_be_deleted(session: Session, pet_id: UUID) -> None:
    if reminder_repository.has_reminders_for_pet(session, pet_id):
        raise _http_error(
            409,
            "PET_IN_USE",
            "宠物仍有关联记录或提醒",
        )


class BoundReminderService:
    """Expose reminder queries with a database session bound for Agent tools."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_reminders(
        self,
        *,
        pet_id: UUID | None = None,
        unlinked: bool = False,
        status: ReminderStatus | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[ReminderRead]:
        return [
            ReminderRead.model_validate(reminder)
            for reminder in list_reminders(
                self._session,
                pet_id=pet_id,
                unlinked=unlinked,
                status=status,
                from_date=from_date,
                to_date=to_date,
            )
        ]
