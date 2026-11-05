"""私人宠物 Vlog（P2，单用户本地版）：条目 CRUD 与本地媒体存储。

媒体文件按生成的存储键写入私有目录（默认 ``./vlog-media``，可用
``PET_AGENT_VLOG_MEDIA_DIR`` 指向仓库外的本地私有目录），数据库只保存条目
与文件元数据。本版仅限回环环境使用：共享部署前需另行补齐真实身份、媒体
访问隔离、位置元数据清理和私有存储。
"""

import os
import re
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.models import VlogMedia, VlogPost
from app.db.repositories import pets as pet_repository
from app.db.repositories import vlogs as vlog_repository
from app.db.repositories.pets import get_local_user
from app.schemas.vlog import (
    IMAGE_MAX_BYTES,
    MAX_IMAGES_PER_VLOG,
    MAX_VIDEOS_PER_VLOG,
    VIDEO_MAX_BYTES,
    VlogCreate,
    VlogMediaRead,
    VlogRead,
    VlogUpdate,
)

STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(jpg|png|mp4)$")
MEDIA_URL_PREFIX = "/api/v1/vlogs/media/"
_SNIFF_SIZE = 16
_COPY_CHUNK = 1024 * 1024


def _error(
    status_code: int, code: str, message: str, retryable: bool = False
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
    )


def media_dir() -> Path:
    """媒体私有目录：默认随运行目录的已忽略路径，可整体指向仓库外。"""
    return Path(os.getenv("PET_AGENT_VLOG_MEDIA_DIR", "./vlog-media"))


def _limit_bytes(media_type: str) -> int:
    return IMAGE_MAX_BYTES if media_type == "image" else VIDEO_MAX_BYTES


def _sniff(file: UploadFile) -> tuple[str, str, str]:
    """按文件头识别实际格式（不信任声明类型与扩展名）。

    返回 ``(media_type, content_type, extension)``。
    """
    head = file.file.read(_SNIFF_SIZE)
    file.file.seek(0)
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg", ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png", ".png"
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return "video", "video/mp4", ".mp4"
    raise _error(400, "VLOG_MEDIA_UNSUPPORTED", "仅支持 JPEG/PNG 图片或 MP4 视频")


def _safe_filename(raw: str | None, extension: str) -> str:
    name = Path(raw or "").name.strip()
    stem = Path(name).stem.strip() if name else ""
    stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", stem)[:80]
    return f"{stem or 'media'}{extension}"


def _copy_stream(file: UploadFile, target: Path, limit: int) -> int:
    """把上传流复制到目标文件并返回字节数；超出上限即中止。"""
    written = 0
    with target.open("wb") as out:
        while True:
            chunk = file.file.read(_COPY_CHUNK)
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)
            if written > limit:
                raise _error(
                    400,
                    "VLOG_MEDIA_TOO_LARGE",
                    "媒体文件超过大小限制（图片 5 MB，视频 20 MB）",
                )
    return written


def _remove_quietly(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # 清理失败仅留下待回收文件，不影响主流程的错误返回。
            pass


def _media_read(row: VlogMedia) -> VlogMediaRead:
    return VlogMediaRead(
        id=UUID(row.id),
        media_type=row.media_type,  # type: ignore[arg-type]
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        url=f"{MEDIA_URL_PREFIX}{row.storage_key}",
        created_at=row.created_at,
    )


def to_read(session: Session, vlog: VlogPost) -> VlogRead:
    media = vlog_repository.list_media_for_vlog(session, vlog.id)
    return VlogRead(
        id=UUID(vlog.id),
        pet_id=UUID(vlog.pet_id),
        caption=vlog.caption,
        occurred_on=vlog.occurred_on,
        media=[_media_read(row) for row in media],
        created_at=vlog.created_at,
        updated_at=vlog.updated_at,
    )


def get_vlog_or_404(session: Session, vlog_id: UUID) -> VlogPost:
    vlog = vlog_repository.get_vlog(session, vlog_id)
    if vlog is None:
        raise _error(404, "VLOG_NOT_FOUND", "未找到 Vlog")
    return vlog


def list_vlogs(
    session: Session,
    *,
    pet_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[VlogRead]:
    if pet_id is not None and pet_repository.get_pet(session, pet_id) is None:
        raise _error(404, "PET_NOT_FOUND", "未找到宠物")
    vlogs = vlog_repository.list_vlogs(
        session, pet_id=pet_id, from_date=from_date, to_date=to_date
    )
    media_rows = vlog_repository.list_media_for_vlogs(
        session, [vlog.id for vlog in vlogs]
    )
    grouped: dict[str, list[VlogMediaRead]] = {vlog.id: [] for vlog in vlogs}
    for row in media_rows:
        grouped[row.vlog_id].append(_media_read(row))
    return [
        VlogRead(
            id=UUID(vlog.id),
            pet_id=UUID(vlog.pet_id),
            caption=vlog.caption,
            occurred_on=vlog.occurred_on,
            media=grouped[vlog.id],
            created_at=vlog.created_at,
            updated_at=vlog.updated_at,
        )
        for vlog in vlogs
    ]


def _validate_upload_plan(
    session: Session, values: VlogCreate, files: list[UploadFile]
) -> list[tuple[UploadFile, str, str, str]]:
    """创建前统一校验：宠物归属、实际格式与数量限制。"""
    if pet_repository.get_pet(session, values.pet_id) is None:
        raise _error(404, "PET_NOT_FOUND", "未找到宠物")
    images = videos = 0
    plan: list[tuple[UploadFile, str, str, str]] = []
    for file in files:
        if file.size == 0:
            raise _error(400, "VLOG_MEDIA_EMPTY", "不能上传空文件")
        media_type, content_type, extension = _sniff(file)
        limit = _limit_bytes(media_type)
        if file.size is not None and file.size > limit:
            raise _error(
                400,
                "VLOG_MEDIA_TOO_LARGE",
                "媒体文件超过大小限制（图片 5 MB，视频 20 MB）",
            )
        if media_type == "image":
            images += 1
        else:
            videos += 1
        if images > MAX_IMAGES_PER_VLOG or videos > MAX_VIDEOS_PER_VLOG:
            raise _error(400, "VLOG_MEDIA_TOO_MANY", "每篇最多 3 张图片或 1 段视频")
        if images and videos:
            raise _error(400, "VLOG_MEDIA_MIXED", "同一篇只能全部是图片或是一段视频")
        plan.append((file, media_type, content_type, extension))
    return plan


def create_vlog(
    session: Session, *, values: VlogCreate, files: list[UploadFile]
) -> VlogRead:
    plan = _validate_upload_plan(session, values, files)
    user = get_local_user(session)
    directory = media_dir()
    written: list[Path] = []
    media_rows: list[dict[str, object]] = []
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for file, media_type, content_type, extension in plan:
            storage_key = f"{uuid4().hex}{extension}"
            target = directory / storage_key
            size = _copy_stream(file, target, _limit_bytes(media_type))
            if size == 0:
                raise _error(400, "VLOG_MEDIA_EMPTY", "不能上传空文件")
            written.append(target)
            media_rows.append(
                {
                    "storage_key": storage_key,
                    "media_type": media_type,
                    "filename": _safe_filename(file.filename, extension),
                    "content_type": content_type,
                    "size_bytes": size,
                }
            )
        vlog = vlog_repository.create_vlog(
            session,
            vlog_id=uuid4(),
            user_id=user.id,
            pet_id=str(values.pet_id),
            caption=values.caption,
            occurred_on=values.occurred_on,
            media=media_rows,
        )
    except HTTPException:
        _remove_quietly(written)
        raise
    except Exception as exc:  # 数据库或磁盘异常：不留下半成品文件
        _remove_quietly(written)
        raise _error(
            500, "VLOG_MEDIA_STORAGE_FAILED", "媒体保存失败，请重试", retryable=True
        ) from exc
    return to_read(session, vlog)


def update_vlog(session: Session, vlog_id: UUID, values: VlogUpdate) -> VlogRead:
    vlog = get_vlog_or_404(session, vlog_id)
    vlog_repository.update_vlog(session, vlog, values.model_dump(exclude_unset=True))
    return to_read(session, vlog)


def delete_vlog(session: Session, vlog_id: UUID) -> None:
    """删除条目并回收媒体：文件先删，失败可整体重试。"""
    vlog = get_vlog_or_404(session, vlog_id)
    keys = [
        row.storage_key for row in vlog_repository.list_media_for_vlog(session, vlog.id)
    ]
    _reclaim_media_files(keys)
    vlog_repository.delete_vlog(session, vlog)


def delete_vlogs_for_pet(session: Session, pet_id: UUID) -> None:
    """删除宠物时同步处理关联媒体（P2 提案）：文件先回收，失败可重试。"""
    keys = vlog_repository.list_storage_keys_for_pet(session, str(pet_id))
    if not keys:
        return
    _reclaim_media_files(keys)
    vlog_repository.delete_vlogs_for_pet(session, str(pet_id))


def _reclaim_media_files(keys: list[str]) -> None:
    directory = media_dir()
    for key in keys:
        try:
            (directory / key).unlink(missing_ok=True)
        except OSError as exc:
            raise _error(
                500,
                "VLOG_MEDIA_CLEANUP_FAILED",
                "媒体文件回收失败，请稍后重试",
                retryable=True,
            ) from exc


def read_media_file(session: Session, storage_key: str) -> tuple[Path, VlogMedia]:
    """经应用路由读取媒体：校验键格式、归属元数据与文件存在性。"""
    if not STORAGE_KEY_PATTERN.match(storage_key):
        raise _error(404, "VLOG_MEDIA_NOT_FOUND", "未找到媒体")
    row = vlog_repository.get_media_by_key(session, storage_key)
    if row is None:
        raise _error(404, "VLOG_MEDIA_NOT_FOUND", "未找到媒体")
    path = media_dir() / storage_key
    if not path.is_file():
        raise _error(404, "VLOG_MEDIA_MISSING", "媒体文件不存在或已被回收")
    return path, row
