from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class PetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"]
    breed: str | None = Field(default=None, max_length=100)
    birthday: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birthday cannot be in the future")
        return value


class PetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"] | None = None
    breed: str | None = Field(default=None, max_length=100)
    birthday: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birthday cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> "PetUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "species" in self.model_fields_set and self.species is None:
            raise ValueError("species cannot be null")
        return self


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    species: Literal["dog", "cat", "other"]
    # P2-1 过渡：DB 列尚未添加、写入路径未开放；from_attributes 校验缺少该
    # 属性的 ORM 对象时回退默认 null，字段在响应中总是出现。
    # 完整后端 PR（含迁移）落地后移除默认值，改为与 breed/notes 一致的
    # 「必填但可空」（str | None），避免漏填路径被默认值静默兜底。
    other_species: str | None = None
    breed: str | None
    birthday: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
