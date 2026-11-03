"""附近服务（P1-8 演示数据版）的请求与响应结构。

字段与 docs/API.md 的 P1-7 契约保持一致：坐标为 WGS84 十进制度数，
距离为非负整数米，来源与回退状态显式区分。
"""

from typing import Literal

from pydantic import BaseModel

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
    navigation_url: str | None
    data_source: NearbyDataSource


class NearbyResponse(BaseModel):
    places: list[Place]
    search_center: SearchCenter
    source: NearbyDataSource
    fallback_reason: FallbackReason
