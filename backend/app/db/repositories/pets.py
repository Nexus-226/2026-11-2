from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DEFAULT_USER_ID, Pet, User


def get_local_user(session: Session) -> User:
    user = session.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(id=DEFAULT_USER_ID, display_name="本地演示用户")
        session.add(user)
        session.commit()
    return user


def list_pets(session: Session) -> list[Pet]:
    return list(
        session.scalars(
            select(Pet)
            .where(Pet.user_id == DEFAULT_USER_ID)
            .order_by(Pet.created_at, Pet.id)
        )
    )


def get_pet(session: Session, pet_id: UUID) -> Pet | None:
    return session.scalar(
        select(Pet).where(
            Pet.id == str(pet_id),
            Pet.user_id == DEFAULT_USER_ID,
        )
    )


def create_pet(session: Session, pet: Pet) -> Pet:
    session.add(pet)
    session.commit()
    session.refresh(pet)
    return pet


def update_pet(session: Session, pet: Pet, values: dict[str, object]) -> Pet:
    for field, value in values.items():
        setattr(pet, field, value)
    session.commit()
    session.refresh(pet)
    return pet


def delete_pet(session: Session, pet: Pet) -> None:
    session.delete(pet)
    session.commit()
