from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Pet
from app.db.repositories import pets as pet_repository
from app.schemas.pet import PetCreate


def list_pets(session: Session) -> list[Pet]:
    pet_repository.get_local_user(session)
    return pet_repository.list_pets(session)


def get_pet(session: Session, pet_id: UUID) -> Pet:
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


def create_pet(session: Session, values: PetCreate) -> Pet:
    user = pet_repository.get_local_user(session)
    pet = Pet(id=str(uuid4()), user_id=user.id, **values.model_dump())
    return pet_repository.create_pet(session, pet)


def update_pet(session: Session, pet_id: UUID, values: dict[str, object]) -> Pet:
    pet = get_pet(session, pet_id)
    return pet_repository.update_pet(session, pet, values)


def delete_pet(session: Session, pet_id: UUID) -> None:
    pet = get_pet(session, pet_id)
    pet_repository.delete_pet(session, pet)
