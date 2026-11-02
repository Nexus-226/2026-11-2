from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Pet
from app.db.repositories import pets as pet_repository
from app.schemas.pet import PetCreate, PetRead


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


def update_pet(session: Session, pet_id: UUID, values: dict[str, object]) -> Pet:
    pet = get_pet_or_404(session, pet_id)
    return pet_repository.update_pet(session, pet, values)


def delete_pet(session: Session, pet_id: UUID) -> None:
    pet = get_pet_or_404(session, pet_id)
    pet_repository.delete_pet(session, pet)
