"""附近服务（P1-8 演示数据版）的请求与响应结构。

字段与 docs/API.md 的 P1-7 契约保持一致：坐标为 WGS84 十进制度数，
距离为非负整数米，来源与回退状态显式区分。
"""

from typing import Literal

from pydantic import BaseModel, field_validator

NearbyCategory = Literal["pet_hospital", "pet_grooming", "pet_store"]
RequestCenterSource = Literal["user_location", "resolved_address"]
CenterSource = Literal["user_location", "resolved_address", "demo_region"]
NearbyDataSource = Literal["amap", "demo"]
FallbackReason = Literal["amap_unavailable", "amap_not_configured"] | None
BusinessStatus = Literal["open", "closed", "unknown"]


class GeoLocation(BaseModel):
    """WGS84 十进制坐标。"""

    lat: float
    lng: float


class SearchCenter(BaseModel):
    """实际用于距离计算的查询中心及其来源。"""

    location: GeoLocation
    source: CenterSource
    label: str


class Place(BaseModel):
    id: str
    name: str
    category: NearbyCategory
    address: str
    phone: str | None
    location: GeoLocation
    distance_m: int
    business_status: BusinessStatus
    # 数据源返回的今日营业时间原文（高德 opentime_today，未解析也原样
    # 返回）；缺失为 null。演示地点没有营业时间数据，恒为 null。
    business_hours_today: str | None
    navigation_url: str | None
    data_source: NearbyDataSource


class NearbyResponse(BaseModel):
    places: list[Place]
    search_center: SearchCenter
    source: NearbyDataSource
    fallback_reason: FallbackReason


AddressResolveSource = Literal["amap"]


class AddressResolveRequest(BaseModel):
    """手动地址解析请求；address 1–200，city 可选 1–20（均去首尾空白）。

    `city` 提供时限定解析城市（前端未填写时按全国搜索说明），不使用
    未授权定位或模型内部知识猜测城市。
    """

    address: str
    city: str | None = None

    @field_validator("address")
    @classmethod
    def _validate_address(cls, value: str) -> str:
        text = value.strip()
        if not 1 <= len(text) <= 200:
            raise ValueError("地址长度需为 1–200 个字符")
        return text

    @field_validator("city")
    @classmethod
    def _validate_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not 1 <= len(text) <= 20:
            raise ValueError("城市长度需为 1–20 个字符")
        return text


class AddressMatch(BaseModel):
    """地址解析候选；`match_kind` 区分地标 POI 与 geocode 来源。

    name/city/district/level 字段恒存在但值可为 null：geocode 候选
    `name` 为 null，POI 候选 `level` 为 null；`level` 为 geocode 的
    高德级别原文（门址/道路/省等），仅作展示精度，不作过滤依据。
    """

    formatted_address: str
    name: str | None
    city: str | None
    district: str | None
    level: str | None
    match_kind: Literal["poi", "geocode"]
    location: GeoLocation
    data_source: AddressResolveSource


class AddressResolveResponse(BaseModel):
    """地址解析结果；多条候选全部返回，由用户选择，不自动选取。"""

    matches: list[AddressMatch]
