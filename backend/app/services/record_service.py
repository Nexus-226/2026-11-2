from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Record
from app.db.repositories import pets as pet_repository
from app.db.repositories import records as record_repository
from app.db.repositories.pets import get_local_user
from app.schemas.record import RecordCreate, RecordUpdate


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": code, "message": message, "retryable": False},
    )


def list_records(
    session: Session,
    *,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    record_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Record]:
    if pet_id is not None and pet_repository.get_pet(session, pet_id) is None:
        raise _not_found("PET_NOT_FOUND", "未找到宠物")
    return record_repository.list_records(
        session,
        pet_id=pet_id,
        unlinked=unlinked,
        record_type=record_type,
        from_date=from_date,
        to_date=to_date,
    )


def get_record_or_404(session: Session, record_id: UUID) -> Record:
    record = record_repository.get_record(session, record_id)
    if record is None:
        raise _not_found("RECORD_NOT_FOUND", "未找到记录")
    return record


def create_record(session: Session, values: RecordCreate) -> Record:
    pet_id = str(values.pet_id) if values.pet_id is not None else None
    if (
        values.pet_id is not None
        and pet_repository.get_pet(session, values.pet_id) is None
    ):
        raise _not_found("PET_NOT_FOUND", "未找到宠物")
    user = get_local_user(session)
    return record_repository.create_record(
        session,
        record_id=uuid4(),
        user_id=user.id,
        pet_id=pet_id,
        record_type=values.record_type,
        occurred_on=values.occurred_on,
        name=values.name,
        weight_kg=values.weight_kg,
        notes=values.notes,
    )


def update_record(session: Session, record_id: UUID, values: RecordUpdate) -> Record:
    record = get_record_or_404(session, record_id)
    update_values = values.model_dump(exclude_unset=True)
    merged_values: dict[str, object] = {
        "pet_id": record.pet_id,
        "record_type": record.record_type,
        "occurred_on": record.occurred_on,
        "name": record.name,
        "weight_kg": record.weight_kg,
        "notes": record.notes,
    }
    merged_values.update(update_values)
    try:
        validated = RecordCreate.model_validate(merged_values)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "更新后的记录字段不符合要求",
                "retryable": False,
            },
        ) from exc

    if validated.pet_id is not None:
        pet_id = str(validated.pet_id)
        if pet_repository.get_pet(session, validated.pet_id) is None:
            raise _not_found("PET_NOT_FOUND", "未找到宠物")
    else:
        pet_id = None

    return record_repository.update_record(
        session,
        record,
        {
            "pet_id": pet_id,
            "record_type": validated.record_type,
            "occurred_on": validated.occurred_on,
            "name": validated.name,
            "weight_kg": validated.weight_kg,
            "notes": validated.notes,
        },
    )


def delete_record(session: Session, record_id: UUID) -> None:
    record_repository.delete_record(session, get_record_or_404(session, record_id))


def ensure_pet_can_be_deleted(session: Session, pet_id: UUID) -> None:
    if record_repository.has_records_for_pet(session, pet_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PET_IN_USE",
                "message": "宠物仍有关联记录",
                "retryable": False,
            },
        )
