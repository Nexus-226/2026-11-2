from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import DEFAULT_USER_ID, VlogMedia, VlogPost


def list_vlogs(
    session: Session,
    *,
    pet_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[VlogPost]:
    statement = select(VlogPost).where(VlogPost.user_id == DEFAULT_USER_ID)
    if pet_id is not None:
        statement = statement.where(VlogPost.pet_id == str(pet_id))
    if from_date is not None:
        statement = statement.where(VlogPost.occurred_on >= from_date)
    if to_date is not None:
        statement = statement.where(VlogPost.occurred_on <= to_date)
    statement = statement.order_by(
        VlogPost.occurred_on.desc(),
        VlogPost.created_at.desc(),
        VlogPost.id.asc(),
    )
    return list(session.scalars(statement))


def get_vlog(session: Session, vlog_id: UUID) -> VlogPost | None:
    return session.scalar(
        select(VlogPost).where(
            VlogPost.id == str(vlog_id),
            VlogPost.user_id == DEFAULT_USER_ID,
        )
    )


def list_media_for_vlog(session: Session, vlog_id: str) -> list[VlogMedia]:
    return list(
        session.scalars(
            select(VlogMedia)
            .where(VlogMedia.vlog_id == vlog_id)
            .order_by(VlogMedia.created_at, VlogMedia.id)
        )
    )


def list_media_for_vlogs(session: Session, vlog_ids: list[str]) -> list[VlogMedia]:
    if not vlog_ids:
        return []
    return list(
        session.scalars(
            select(VlogMedia)
            .where(VlogMedia.vlog_id.in_(vlog_ids))
            .order_by(VlogMedia.vlog_id, VlogMedia.created_at, VlogMedia.id)
        )
    )


def get_media_by_key(session: Session, storage_key: str) -> VlogMedia | None:
    return session.scalar(select(VlogMedia).where(VlogMedia.storage_key == storage_key))


def list_storage_keys_for_pet(session: Session, pet_id: str) -> list[str]:
    return list(
        session.scalars(
            select(VlogMedia.storage_key)
            .join(VlogPost, VlogMedia.vlog_id == VlogPost.id)
            .where(VlogPost.pet_id == pet_id)
        )
    )


def create_vlog(
    session: Session,
    *,
    vlog_id: UUID,
    user_id: str,
    pet_id: str,
    caption: str | None,
    occurred_on: date,
    media: list[dict[str, object]],
) -> VlogPost:
    vlog = VlogPost(
        id=str(vlog_id),
        user_id=user_id,
        pet_id=pet_id,
        caption=caption,
        occurred_on=occurred_on,
    )
    session.add(vlog)
    for item in media:
        session.add(
            VlogMedia(
                id=str(uuid4()),
                vlog_id=vlog.id,
                storage_key=str(item["storage_key"]),
                media_type=str(item["media_type"]),
                filename=str(item["filename"]),
                content_type=str(item["content_type"]),
                size_bytes=int(item["size_bytes"]),
            )
        )
    session.commit()
    session.refresh(vlog)
    return vlog


def update_vlog(
    session: Session, vlog: VlogPost, values: dict[str, object]
) -> VlogPost:
    for field, value in values.items():
        setattr(vlog, field, value)
    session.commit()
    session.refresh(vlog)
    return vlog


def delete_vlog(session: Session, vlog: VlogPost) -> None:
    session.execute(delete(VlogMedia).where(VlogMedia.vlog_id == vlog.id))
    session.delete(vlog)
    session.commit()


def delete_vlogs_for_pet(session: Session, pet_id: str) -> int:
    """删除某宠物的全部 Vlog（含媒体元数据），返回删除的条目数。

    媒体文件的回收由服务层在删除行之前完成（失败可重试）。
    """
    vlog_ids = list(
        session.scalars(
            select(VlogPost.id).where(
                VlogPost.user_id == DEFAULT_USER_ID,
                VlogPost.pet_id == pet_id,
            )
        )
    )
    if not vlog_ids:
        return 0
    session.execute(delete(VlogMedia).where(VlogMedia.vlog_id.in_(vlog_ids)))
    session.execute(
        delete(VlogPost).where(
            VlogPost.user_id == DEFAULT_USER_ID,
            VlogPost.pet_id == pet_id,
        )
    )
    session.commit()
    return len(vlog_ids)
