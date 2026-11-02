from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.models import Pet
from app.db.session import get_db
from app.schemas.pet import PetCreate, PetRead, PetUpdate
from app.services import pet_service

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[PetRead])
def list_pets(session: DbSession) -> list[Pet]:
    return pet_service.list_pets(session)


@router.post("", response_model=PetRead, status_code=status.HTTP_201_CREATED)
def create_pet(pet_in: PetCreate, session: DbSession) -> Pet:
    return pet_service.create_pet(session, pet_in)


@router.get("/{pet_id}", response_model=PetRead)
def get_pet(pet_id: UUID, session: DbSession) -> Pet:
    return pet_service.get_pet_or_404(session, pet_id)


@router.patch("/{pet_id}", response_model=PetRead)
def update_pet(pet_id: UUID, pet_in: PetUpdate, session: DbSession) -> Pet:
    return pet_service.update_pet(
        session, pet_id, pet_in.model_dump(exclude_unset=True)
    )


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(pet_id: UUID, session: DbSession) -> Response:
    pet_service.delete_pet(session, pet_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
