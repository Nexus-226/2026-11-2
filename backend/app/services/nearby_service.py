"""附近服务（P1-8 演示数据版）。

当前阶段未接入高德（P1-9 单独提交）：`/api/v1/nearby` 按契约回退到内置
演示种子数据，沿用请求中的查询中心计算距离并保留查询中心来源；
`/api/v1/nearby/demo` 使用配置的 WGS84 演示中心。所有演示地点均为虚构
数据，`data_source` 与 ID 保持 `demo` 前缀，页面与 Agent 必须明确标注
演示来源，不得描述为实时结果。
"""

import logging
import math
import os
from dataclasses import dataclass

from fastapi import HTTPException

from app.schemas.nearby import (
    BusinessStatus,
    GeoLocation,
    NearbyCategory,
    NearbyResponse,
    Place,
    RequestCenterSource,
    SearchCenter,
)

logger = logging.getLogger(__name__)

DEFAULT_DEMO_CENTER = GeoLocation(lat=39.9001, lng=116.4001)
DEMO_REGION_LABEL = "演示区域（非实时位置）"
CENTER_LABELS: dict[str, str] = {
    "user_location": "当前位置",
    "resolved_address": "所选地址",
}

# 平均地球半径（米），用于 WGS84 球面距离计算。
EARTH_RADIUS_M = 6371008.8


@dataclass(frozen=True)
class DemoPlaceSeed:
    """演示地点种子：位置以相对演示中心的经纬度偏移表示（WGS84）。

    偏移让种子地点始终分布在配置的演示中心周围，保证演示区域入口
    在任何合法配置下都能提供三类地点；距离仍按真实球面距离计算。
    """

    key: str
    name: str
    category: NearbyCategory
    address: str
    phone: str | None
    business_status: BusinessStatus
    lat_offset: float
    lng_offset: float


DEMO_PLACE_SEEDS: list[DemoPlaceSeed] = [
    DemoPlaceSeed(
        key="pet-hospital-01",
        name="安心宠物医院（示例）",
        category="pet_hospital",
        address="演示区幸福路 1 号",
        phone="010-0000-0001",
        business_status="open",
        lat_offset=0.004,
        lng_offset=0.002,
    ),
    DemoPlaceSeed(
        key="pet-hospital-02",
        name="示例路宠物诊所",
        category="pet_hospital",
        address="演示区示例路 18 号",
        phone=None,
        business_status="unknown",
        lat_offset=0.02,
        lng_offset=-0.01,
    ),
    DemoPlaceSeed(
        key="pet-hospital-03",
        name="示例动物医院",
        category="pet_hospital",
        address="演示区环路 88 号",
        phone="010-0000-0003",
        business_status="closed",
        lat_offset=0.09,
        lng_offset=0.03,
    ),
    DemoPlaceSeed(
        key="pet-grooming-01",
        name="示例宠物美容屋",
        category="pet_grooming",
        address="演示区阳光巷 6 号",
        phone="010-0000-0002",
        business_status="open",
        lat_offset=0.008,
        lng_offset=-0.004,
    ),
    DemoPlaceSeed(
        key="pet-grooming-02",
        name="示例萌宠 SPA",
        category="pet_grooming",
        address="演示区花园街 22 号",
        phone=None,
        business_status="closed",
        lat_offset=0.035,
        lng_offset=0.02,
    ),
    DemoPlaceSeed(
        key="pet-grooming-03",
        name="示例宠物造型沙龙",
        category="pet_grooming",
        address="演示区月桂路 9 号",
        phone="010-0000-0005",
        business_status="unknown",
        lat_offset=0.07,
        lng_offset=-0.03,
    ),
    DemoPlaceSeed(
        key="pet-store-01",
        name="示例宠物用品店",
        category="pet_store",
        address="演示区集市街 3 号",
        phone="010-0000-0004",
        business_status="open",
        lat_offset=0.012,
        lng_offset=0.008,
    ),
    DemoPlaceSeed(
        key="pet-store-02",
        name="示例宠物超市",
        category="pet_store",
        address="演示区大道 200 号",
        phone=None,
        business_status="open",
        lat_offset=0.05,
        lng_offset=-0.025,
    ),
    DemoPlaceSeed(
        key="pet-store-03",
        name="示例宠物百货",
        category="pet_store",
        address="演示区南街 45 号",
        phone="010-0000-0006",
        business_status="unknown",
        lat_offset=0.11,
        lng_offset=0.05,
    ),
]


def _env_float(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("环境变量 %s 不是有效数字，使用默认值 %s", name, default)
        return default
    if not low <= value <= high:
        logger.warning(
            "环境变量 %s 超出 [%s, %s]，使用默认值 %s", name, low, high, default
        )
        return default
    return value


def get_demo_center() -> GeoLocation:
    """演示中心由部署配置（WGS84）；未配置或非法时使用默认演示中心。"""
    return GeoLocation(
        lat=_env_float(
            "PET_AGENT_DEMO_CENTER_LAT", DEFAULT_DEMO_CENTER.lat, -90.0, 90.0
        ),
        lng=_env_float(
            "PET_AGENT_DEMO_CENTER_LNG", DEFAULT_DEMO_CENTER.lng, -180.0, 180.0
        ),
    )


def spherical_distance_m(from_point: GeoLocation, to_point: GeoLocation) -> int:
    """WGS84 球面距离（haversine），四舍五入为非负整数米。"""
    lat1 = math.radians(from_point.lat)
    lat2 = math.radians(to_point.lat)
    dlat = math.radians(to_point.lat - from_point.lat)
    dlng = math.radians(to_point.lng - from_point.lng)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return math.floor(2 * EARTH_RADIUS_M * math.asin(math.sqrt(a)) + 0.5)


def _seed_location(seed: DemoPlaceSeed, demo_center: GeoLocation) -> GeoLocation:
    return GeoLocation(
        lat=round(demo_center.lat + seed.lat_offset, 6),
        lng=round(demo_center.lng + seed.lng_offset, 6),
    )


def _to_place(
    seed: DemoPlaceSeed, location: GeoLocation, query_center: GeoLocation
) -> Place:
    return Place(
        id=f"demo:{seed.key}",
        name=seed.name,
        category=seed.category,
        address=seed.address,
        phone=seed.phone,
        location=location,
        distance_m=spherical_distance_m(query_center, location),
        business_status=seed.business_status,
        navigation_url=None,
        data_source="demo",
    )


def _places_for_category(
    category: NearbyCategory, query_center: GeoLocation
) -> list[Place]:
    demo_center = get_demo_center()
    return [
        _to_place(seed, _seed_location(seed, demo_center), query_center)
        for seed in DEMO_PLACE_SEEDS
        if seed.category == category
    ]


def _filter_and_sort(places: list[Place], radius_m: int) -> list[Place]:
    in_radius = [place for place in places if place.distance_m <= radius_m]
    in_radius.sort(key=lambda place: (place.distance_m, place.id))
    return in_radius


def search_nearby(
    *,
    lat: float,
    lng: float,
    category: NearbyCategory,
    radius_m: int,
    center_source: RequestCenterSource,
) -> NearbyResponse:
    query_center = GeoLocation(lat=lat, lng=lng)
    # P1-8：高德适配器尚未接入（P1-9 单独提交），按契约回退演示种子数据：
    # 沿用原查询中心计算距离、保留请求中的查询中心来源，不切换到演示中心。
    # 演示种子可能离查询中心较远，此处允许 places 为空。
    return NearbyResponse(
        places=_filter_and_sort(_places_for_category(category, query_center), radius_m),
        search_center=SearchCenter(
            location=query_center,
            source=center_source,
            label=CENTER_LABELS.get(center_source, "当前位置"),
        ),
        source="demo",
        fallback_reason="amap_not_configured",
    )


def search_demo_region(*, category: NearbyCategory, radius_m: int) -> NearbyResponse:
    demo_center = get_demo_center()
    return NearbyResponse(
        places=_filter_and_sort(_places_for_category(category, demo_center), radius_m),
        search_center=SearchCenter(
            location=demo_center, source="demo_region", label=DEMO_REGION_LABEL
        ),
        source="demo",
        fallback_reason=None,
    )


def _place_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "PLACE_NOT_FOUND",
            "message": "未找到地点",
            "retryable": False,
        },
    )


def get_place(place_id: str, *, lat: float, lng: float) -> Place:
    """按 ID 来源查询：`demo:` 只查演示目录，`amap:` 不回退演示数据。"""
    if place_id.startswith("amap:"):
        # P1-9 接入高德前，真实地点详情不可用；不静默替换成演示地点。
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "高德服务未配置，暂不能查询真实地点详情",
                "retryable": False,
            },
        )
    if not place_id.startswith("demo:"):
        raise _place_not_found()
    key = place_id[len("demo:") :]
    seed = next((item for item in DEMO_PLACE_SEEDS if item.key == key), None)
    if seed is None:
        raise _place_not_found()
    query_center = GeoLocation(lat=lat, lng=lng)
    return _to_place(seed, _seed_location(seed, get_demo_center()), query_center)
