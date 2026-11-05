from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.models import DEFAULT_USER_ID, VlogMedia, VlogMediaCleanup, VlogPost


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
    return vlog


def update_vlog(
    session: Session, vlog: VlogPost, values: dict[str, object]
) -> VlogPost:
    for field, value in values.items():
        setattr(vlog, field, value)
    session.commit()
    session.refresh(vlog)
    return vlog


def lock_writes(session: Session) -> None:
    # SQLite does not lock on SELECT. Serialize the pet check and related writes.
    if session.get_bind().dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))


def _queue_media_cleanup(session: Session, vlog_ids: list[str]) -> None:
    media_filter = VlogMedia.vlog_id.in_(vlog_ids)
    storage_keys = session.scalars(select(VlogMedia.storage_key).where(media_filter))
    session.add_all(VlogMediaCleanup(storage_key=key) for key in storage_keys)
    session.execute(delete(VlogMedia).where(media_filter))


def delete_vlog(session: Session, vlog: VlogPost) -> None:
    _queue_media_cleanup(session, [vlog.id])
    session.delete(vlog)
    session.commit()


def delete_vlogs_for_pet(session: Session, pet_id: str) -> None:
    pet_vlogs = select(VlogPost.id).where(
        VlogPost.user_id == DEFAULT_USER_ID,
        VlogPost.pet_id == pet_id,
    )
    vlog_ids = list(session.scalars(pet_vlogs))
    if vlog_ids:
        _queue_media_cleanup(session, vlog_ids)
        session.execute(delete(VlogPost).where(VlogPost.id.in_(vlog_ids)))


def pending_media_cleanup(session: Session) -> list[str]:
    return list(session.scalars(select(VlogMediaCleanup.storage_key)))


def finish_media_cleanup(session: Session, storage_keys: list[str]) -> None:
    if storage_keys:
        session.execute(
            delete(VlogMediaCleanup).where(
                VlogMediaCleanup.storage_key.in_(storage_keys)
            )
        )
    session.commit()
