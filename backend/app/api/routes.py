from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import agent_runtime, nearby_service, pet_service
from app.config import DEMO_USER_ID
from app.schemas import ChatRequest, ChatResponse, NearbyQuery, NearbyResponse, Pet, PetCreate, PetUpdate, PlaceCategory

router = APIRouter(prefix="/api/v1")
DemoUser = Annotated[str, Query(pattern=f"^{DEMO_USER_ID}$")]


@router.get("/pets", response_model=list[Pet])
def list_pets(user_id: DemoUser = DEMO_USER_ID) -> list[Pet]:
    return pet_service.list(user_id)


@router.post("/pets", response_model=Pet, status_code=status.HTTP_201_CREATED)
def create_pet(payload: PetCreate) -> Pet:
    return pet_service.create(payload)


@router.get("/pets/{pet_id}", response_model=Pet)
def get_pet(pet_id: str, user_id: DemoUser = DEMO_USER_ID) -> Pet:
    pet = pet_service.get(user_id, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet was not found")
    return pet


@router.patch("/pets/{pet_id}", response_model=Pet)
def update_pet(pet_id: str, payload: PetUpdate) -> Pet:
    pet = pet_service.update(pet_id, payload)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet was not found")
    return pet


@router.delete("/pets/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(pet_id: str, user_id: DemoUser = DEMO_USER_ID) -> Response:
    if not pet_service.delete(user_id, pet_id):
        raise HTTPException(status_code=404, detail="Pet was not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return agent_runtime.chat(payload, request_id=f"req_{uuid4().hex[:12]}")


@router.get("/nearby", response_model=NearbyResponse)
def nearby(user_id: DemoUser = DEMO_USER_ID, lat: float | None = Query(default=None, ge=-90, le=90), lng: float | None = Query(default=None, ge=-180, le=180), address: str | None = Query(default=None, min_length=2, max_length=200), category: PlaceCategory | None = None) -> NearbyResponse:
    del user_id
    return nearby_service.search(NearbyQuery(lat=lat, lng=lng, address=address, category=category))
