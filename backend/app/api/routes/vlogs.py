from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.vlog import VlogCreate, VlogRead, VlogUpdate
from app.services import vlog_service

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


def _form_error(exc: ValidationError) -> HTTPException:
    message = "请求字段缺失或不符合要求"
    for error in exc.errors():
        msg = error.get("msg")
        if isinstance(msg, str) and msg.startswith("Value error, "):
            message = msg.removeprefix("Value error, ")
            break
    return HTTPException(
        status_code=422,
        detail={"code": "VALIDATION_ERROR", "message": message, "retryable": False},
    )


@router.get("", response_model=list[VlogRead])
def list_vlogs(
    session: DbSession,
    pet_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[VlogRead]:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "开始日期不能晚于结束日期",
                "retryable": False,
            },
        )
    return vlog_service.list_vlogs(
        session, pet_id=pet_id, from_date=from_date, to_date=to_date
    )


@router.post("", response_model=VlogRead, status_code=status.HTTP_201_CREATED)
def create_vlog(
    session: DbSession,
    pet_id: Annotated[UUID, Form()],
    occurred_on: Annotated[date, Form()],
    caption: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> VlogRead:
    """创建 Vlog：multipart 表单，选传最多 3 张图片或 1 段视频。"""
    try:
        values = VlogCreate(pet_id=pet_id, occurred_on=occurred_on, caption=caption)
    except ValidationError as exc:
        raise _form_error(exc) from exc
    return vlog_service.create_vlog(session, values=values, files=files or [])


@router.get("/media/{storage_key}", response_class=FileResponse)
def get_vlog_media(storage_key: str, session: DbSession) -> FileResponse:
    path, row = vlog_service.read_media_file(session, storage_key)
    return FileResponse(path, media_type=row.content_type, filename=row.filename)


@router.get("/{vlog_id}", response_model=VlogRead)
def get_vlog(vlog_id: UUID, session: DbSession) -> VlogRead:
    return vlog_service.to_read(session, vlog_service.get_vlog_or_404(session, vlog_id))


@router.patch("/{vlog_id}", response_model=VlogRead)
def update_vlog(vlog_id: UUID, values: VlogUpdate, session: DbSession) -> VlogRead:
    return vlog_service.update_vlog(session, vlog_id, values)


@router.delete("/{vlog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vlog(vlog_id: UUID, session: DbSession) -> Response:
    vlog_service.delete_vlog(session, vlog_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
