from uuid import uuid4

from app.config import DEMO_USER_ID
from app.schemas import Pet, PetCreate, PetUpdate


class PetService:
    """In-memory P0 repository boundary; replaceable with SQLite later."""

    def __init__(self) -> None:
        demo = Pet(id="pet-demo-001", user_id=DEMO_USER_ID, name="团子", species="cat", breed="British Shorthair", age_years=3, health_notes="需要控制体重")
        self._pets: dict[str, Pet] = {demo.id: demo}

    def list(self, user_id: str) -> list[Pet]:
        return [pet for pet in self._pets.values() if pet.user_id == user_id]

    def get(self, user_id: str, pet_id: str) -> Pet | None:
        pet = self._pets.get(pet_id)
        return pet if pet and pet.user_id == user_id else None

    def create(self, payload: PetCreate) -> Pet:
        pet = Pet(id=f"pet-{uuid4().hex[:8]}", **payload.model_dump())
        self._pets[pet.id] = pet
        return pet

    def update(self, pet_id: str, payload: PetUpdate) -> Pet | None:
        current = self.get(payload.user_id, pet_id)
        if not current:
            return None
        updates = payload.model_dump(exclude={"user_id"}, exclude_unset=True)
        updated = current.model_copy(update=updates)
        self._pets[pet_id] = updated
        return updated

    def delete(self, user_id: str, pet_id: str) -> bool:
        if not self.get(user_id, pet_id):
            return False
        del self._pets[pet_id]
        return True
