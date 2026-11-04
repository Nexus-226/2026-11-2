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

OTHER_SPECIES_MAX_LENGTH = 50

# P2-1 契约：关联冲突沿用 422 VALIDATION_ERROR 与统一错误结构，message 需区分
# 「dog/cat 携带非空具体物种」与「从 other 切回猫狗时未显式清空原具体物种」，
# 便于定位表单问题；不新增错误码或响应字段（见 docs/API.md）。
ERROR_OTHER_SPECIES_NOT_ALLOWED = (
    "other_species must be null when species is dog or cat"
)
ERROR_OTHER_SPECIES_NOT_CLEARED = (
    "species cannot be changed to dog or cat while other_species is still "
    "set; clear it explicitly with null first"
)


def normalize_other_species(value: str | None) -> str | None:
    """按 P2-1 契约标准化 other_species。

    仅去除首尾空白；去除后为空等同 `null`；不做 NFC 等 Unicode 归一化，
    不改写其余字符，不折叠内部空白。长度按标准化后的 Unicode 码点计数。
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > OTHER_SPECIES_MAX_LENGTH:
        raise ValueError(
            f"other_species must be at most {OTHER_SPECIES_MAX_LENGTH} characters"
        )
    return value


class PetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"]
    # P2-1：other 的具体物种档案字段；仅接受字符串或 null，数字、布尔值、
    # 数组和对象均返回 422。创建时省略等同 null。
    other_species: str | None = None
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

    @field_validator("other_species")
    @classmethod
    def normalize_other_species_value(cls, value: str | None) -> str | None:
        return normalize_other_species(value)

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birthday cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_species_pair(self) -> "PetCreate":
        if self.species in ("dog", "cat") and self.other_species:
            raise ValueError(ERROR_OTHER_SPECIES_NOT_ALLOWED)
        return self


class PetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    species: Literal["dog", "cat", "other"] | None = None
    # P2-1：PATCH 省略表示不修改；显式 null 是合法清空操作，不套用
    # name/species 的非空守卫。
    other_species: str | None = None
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

    @field_validator("other_species")
    @classmethod
    def normalize_other_species_value(cls, value: str | None) -> str | None:
        return normalize_other_species(value)

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
        # 同一请求体中已明确的冲突在此提前拦截；跨库状态的完整对象校验由
        # Service 合并原资料后执行（见 app.services.pet_service），两者缺一不可。
        if (
            self.species in ("dog", "cat")
            and "other_species" in self.model_fields_set
            and self.other_species is not None
        ):
            raise ValueError(ERROR_OTHER_SPECIES_NOT_ALLOWED)
        return self


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    species: Literal["dog", "cat", "other"]
    # P2-1：与 breed/notes 一致的「必填但可空」字段，响应中总是出现；
    # dog/cat 时为 null（由写入侧联合校验保证）。
    other_species: str | None
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
