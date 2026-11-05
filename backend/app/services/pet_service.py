from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Pet
from app.db.repositories import pets as pet_repository
from app.schemas.pet import (
    ERROR_OTHER_SPECIES_NOT_ALLOWED,
    ERROR_OTHER_SPECIES_NOT_CLEARED,
    PetCreate,
    PetRead,
)
from app.services.record_service import ensure_pet_can_be_deleted
from app.services.reminder_service import (
    ensure_pet_can_be_deleted as ensure_pet_has_no_reminders,
)
from app.services.vlog_service import delete_vlogs_for_pet as delete_pet_vlogs


def list_pets(session: Session) -> list[Pet]:
    pet_repository.get_local_user(session)
    return pet_repository.list_pets(session)


def get_pet(session: Session, pet_id: UUID) -> Pet | None:
    return pet_repository.get_pet(session, pet_id)


def get_pet_or_404(session: Session, pet_id: UUID) -> Pet:
    pet = pet_repository.get_pet(session, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PET_NOT_FOUND",
                "message": "未找到宠物",
                "retryable": False,
            },
        )
    return pet


class BoundPetService:
    """Expose pet operations with a database session bound for Agent tools."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        pet = get_pet(self._session, pet_id)
        return PetRead.model_validate(pet) if pet is not None else None

    def list_pets(self) -> list[PetRead]:
        return [PetRead.model_validate(pet) for pet in list_pets(self._session)]


def create_pet(session: Session, values: PetCreate) -> Pet:
    user = pet_repository.get_local_user(session)
    pet = Pet(id=str(uuid4()), user_id=user.id, **values.model_dump())
    return pet_repository.create_pet(session, pet)


def _validate_species_pair_on_update(pet: Pet, values: dict[str, object]) -> None:
    """PATCH 合并原资料后的完整对象联合校验（P2-1 契约）。

    仅凭 PetUpdate 请求体无法判断省略 species 时的实际物种，因此以合并后的
    完整候选对象为准；同一请求体中已明确的冲突由 Schema 提前拦截，这里兜底
    跨库状态冲突。校验在写入前执行，失败不产生任何部分修改。
    """
    species = values.get("species", pet.species)
    other_species = values.get("other_species", pet.other_species)
    if species not in ("dog", "cat") or not other_species:
        return
    if "species" in values and values["species"] != pet.species:
        # 切换到 dog/cat 时未显式清空原具体物种（省略字段不自动清空）。
        message = ERROR_OTHER_SPECIES_NOT_CLEARED
    else:
        # dog/cat 携带非空具体物种。
        message = ERROR_OTHER_SPECIES_NOT_ALLOWED
    raise HTTPException(
        status_code=422,
        detail={"code": "VALIDATION_ERROR", "message": message, "retryable": False},
    )


def update_pet(session: Session, pet_id: UUID, values: dict[str, object]) -> Pet:
    pet = get_pet_or_404(session, pet_id)
    _validate_species_pair_on_update(pet, values)
    return pet_repository.update_pet(session, pet, values)


def delete_pet(session: Session, pet_id: UUID) -> None:
    pet = get_pet_or_404(session, pet_id)
    ensure_pet_can_be_deleted(session, pet_id)
    ensure_pet_has_no_reminders(session, pet_id)
    # P2 提案：删除宠物时同步处理关联 Vlog 媒体（文件先回收，失败可重试）。
    delete_pet_vlogs(session, pet_id)
    pet_repository.delete_pet(session, pet)
