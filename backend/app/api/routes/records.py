from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.models import Record
from app.db.session import get_db
from app.schemas.record import RecordCreate, RecordRead, RecordType, RecordUpdate
from app.services import record_service

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[RecordRead])
def list_records(
    session: DbSession,
    pet_id: UUID | None = None,
    unlinked: bool = False,
    record_type: RecordType | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Record]:
    if unlinked and pet_id is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "unlinked 与 pet_id 不能同时使用",
                "retryable": False,
            },
        )
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "开始日期不能晚于结束日期",
                "retryable": False,
            },
        )
    return record_service.list_records(
        session,
        pet_id=pet_id,
        unlinked=unlinked,
        record_type=record_type,
        from_date=from_date,
        to_date=to_date,
    )


@router.post("", response_model=RecordRead, status_code=status.HTTP_201_CREATED)
def create_record(record_in: RecordCreate, session: DbSession) -> Record:
    return record_service.create_record(session, record_in)


@router.get("/{record_id}", response_model=RecordRead)
def get_record(record_id: UUID, session: DbSession) -> Record:
    return record_service.get_record_or_404(session, record_id)


@router.patch("/{record_id}", response_model=RecordRead)
def update_record(
    record_id: UUID, record_in: RecordUpdate, session: DbSession
) -> Record:
    return record_service.update_record(session, record_id, record_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: UUID, session: DbSession) -> Response:
    record_service.delete_record(session, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
