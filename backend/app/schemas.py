from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.config import DEMO_USER_ID


class PetBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    species: str = Field(min_length=1, max_length=40)
    breed: str | None = Field(default=None, max_length=80)
    age_years: float | None = Field(default=None, ge=0, le=80)
    health_notes: str | None = Field(default=None, max_length=1000)


class PetCreate(PetBase):
    user_id: Literal[DEMO_USER_ID] = DEMO_USER_ID


class PetUpdate(BaseModel):
    user_id: Literal[DEMO_USER_ID] = DEMO_USER_ID
    name: str | None = Field(default=None, min_length=1, max_length=80)
    species: str | None = Field(default=None, min_length=1, max_length=40)
    breed: str | None = Field(default=None, max_length=80)
    age_years: float | None = Field(default=None, ge=0, le=80)
    health_notes: str | None = Field(default=None, max_length=1000)


class Pet(PetBase):
    id: str
    user_id: str


class ChatRequest(BaseModel):
    user_id: Literal[DEMO_USER_ID] = DEMO_USER_ID
    session_id: str | None = Field(default=None, max_length=100)
    pet_id: str | None = Field(default=None, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class ToolStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ToolResult(BaseModel):
    tool: str
    status: ToolStatus
    data: dict[str, Any] | None = None
    message: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    reply: str
    used_pet_id: str | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)


class PlaceCategory(StrEnum):
    HOSPITAL = "pet_hospital"
    GROOMING = "pet_grooming"
    STORE = "pet_store"


class Place(BaseModel):
    id: str
    name: str
    category: PlaceCategory
    address: str
    phone: str | None = None
    lat: float
    lng: float
    distance_m: int
    business_status: str | None = None
    data_source: str


class NearbyResponse(BaseModel):
    places: list[Place]
    input_crs: str = "WGS-84"
    provider_crs: str
    coordinate_converted: bool
    location_source: Literal["browser", "manual_address_mock"]


class NearbyQuery(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, min_length=2, max_length=200)
    category: PlaceCategory | None = None

    @model_validator(mode="after")
    def location_is_complete(self) -> "NearbyQuery":
        has_coordinates = self.lat is not None or self.lng is not None
        if has_coordinates and (self.lat is None or self.lng is None):
            raise ValueError("lat and lng must be provided together")
        if self.lat is None and not self.address:
            raise ValueError("provide coordinates or a manual address")
        return self
