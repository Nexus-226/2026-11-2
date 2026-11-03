"""附近服务（P1-8 演示数据版；P1-9 高德真实接入）。

配置 `AMAP_WEB_SERVICE_KEY` 后，`/api/v1/nearby` 通过高德 Web 服务 v5
查询真实 POI：请求前把 WGS84 转为 GCJ-02，返回的 GCJ-02 坐标转回
WGS84，按服务端球面距离过滤半径，以 `(distance_m, id)` 稳定排序并按
高德地点 ID 去重；高德未配置或调用失败时按契约回落演示种子数据，并
分别以 `fallback_reason` 的 `amap_not_configured`/`amap_unavailable`
标注，回落时沿用请求中的查询中心与来源。`/api/v1/nearby/demo` 仍使用
配置的演示中心。所有演示地点均为虚构数据，`data_source` 与 ID 保持
`demo` 前缀，页面与 Agent 必须明确标注演示来源，不得描述为实时结果。
"""

import logging
import math
import os
from dataclasses import dataclass

from fastapi import HTTPException

from app.schemas.nearby import (
    AddressMatch,
    AddressResolveResponse,
    BusinessStatus,
    FallbackReason,
    GeoLocation,
    NearbyCategory,
    NearbyResponse,
    Place,
    RequestCenterSource,
    SearchCenter,
)
from app.services.amap import AMapClient, AMapPlace, AMapTimeout, AMapUnavailable

logger = logging.getLogger(__name__)

DEFAULT_DEMO_CENTER = GeoLocation(lat=39.9001, lng=116.4001)
DEMO_REGION_LABEL = "演示区域（非实时位置）"
CENTER_LABELS: dict[str, str] = {
    "user_location": "当前位置",
    "resolved_address": "所选地址",
}

# P1-9：高德周边搜索按类别使用的关键字（v5 支持多个用“|”分割）。
# 不使用 POI 分类码：分类码表需人工维护且易错配，关键字对“宠物医院/
# 宠物美容/宠物用品”这类明确词的召回稳定。
AMAP_KEYWORDS: dict[NearbyCategory, str] = {
    "pet_hospital": "宠物医院|动物医院",
    "pet_grooming": "宠物美容|宠物SPA|宠物洗护",
    "pet_store": "宠物用品|宠物店",
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
    # 演示中心允许配置到 WGS84 边界（如纬度 90、经度 180）；偏移后必须收敛回
    # 合法范围（纬度 [-90, 90]、经度 [-180, 180]），保证任何合法配置下
    # 响应中的地点坐标都不会越界。
    lat = demo_center.lat + seed.lat_offset
    lng = demo_center.lng + seed.lng_offset
    return GeoLocation(
        lat=round(max(-90.0, min(90.0, lat)), 6),
        lng=round(max(-180.0, min(180.0, lng)), 6),
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


def _amap_api_key() -> str:
    """高德密钥仅由后端读取；留白视为未接入。"""
    return os.getenv("AMAP_WEB_SERVICE_KEY", "").strip()


def _amap_client() -> AMapClient:
    # 测试通过 monkeypatch 本函数注入带 MockTransport 的客户端。
    return AMapClient(api_key=_amap_api_key())


def _amap_to_place(
    poi: AMapPlace, category: NearbyCategory, query_center: GeoLocation
) -> Place:
    location = GeoLocation(lat=poi.lat, lng=poi.lng)
    # 高德不提供可靠的营业状态与导航链接，按契约分别置为 unknown/None。
    return Place(
        id=f"amap:{poi.poi_id}",
        name=poi.name,
        category=category,
        address=poi.address,
        phone=poi.phone,
        location=location,
        distance_m=spherical_distance_m(query_center, location),
        business_status="unknown",
        navigation_url=None,
        data_source="amap",
    )


def _category_from_amap_type(type_name: str) -> NearbyCategory:
    """按高德 POI 类型文本归入三类地点；无法识别时归入宠物用品店。"""
    text = (type_name or "").lower()
    if any(word in text for word in ("美容", "spa", "洗护", "造型")):
        return "pet_grooming"
    if any(word in text for word in ("医院", "诊所", "门诊", "兽医", "动物医疗")):
        return "pet_hospital"
    if any(word in text for word in ("商店", "超市", "用品", "门店", "宠物店", "水族")):
        return "pet_store"
    return "pet_store"


def _demo_fallback(
    search_center: SearchCenter,
    category: NearbyCategory,
    radius_m: int,
    reason: FallbackReason,
) -> NearbyResponse:
    # 演示种子可能离查询中心较远，此处允许 places 为空。
    return NearbyResponse(
        places=_filter_and_sort(
            _places_for_category(category, search_center.location), radius_m
        ),
        search_center=search_center,
        source="demo",
        fallback_reason=reason,
    )


def search_nearby(
    *,
    lat: float,
    lng: float,
    category: NearbyCategory,
    radius_m: int,
    center_source: RequestCenterSource,
) -> NearbyResponse:
    query_center = GeoLocation(lat=lat, lng=lng)
    search_center = SearchCenter(
        location=query_center,
        source=center_source,
        label=CENTER_LABELS.get(center_source, "当前位置"),
    )
    if not _amap_api_key():
        # 未配置高德：沿用原查询中心回落演示种子数据。
        return _demo_fallback(search_center, category, radius_m, "amap_not_configured")
    try:
        pois = _amap_client().search_around(
            lat=lat, lng=lng, keywords=AMAP_KEYWORDS[category], radius_m=radius_m
        )
    except (AMapTimeout, AMapUnavailable) as exc:
        # 高德不可用：按契约回落演示数据并标注，不切换查询中心。
        logger.warning("附近查询高德失败，回落演示数据：%s", exc)
        return _demo_fallback(search_center, category, radius_m, "amap_unavailable")
    # 去重：同一高德地点 ID 只保留首个；距离过滤与稳定排序由服务端负责。
    deduped: dict[str, Place] = {}
    for poi in pois:
        place = _amap_to_place(poi, category, query_center)
        deduped.setdefault(place.id, place)
    return NearbyResponse(
        places=_filter_and_sort(list(deduped.values()), radius_m),
        search_center=search_center,
        source="amap",
        fallback_reason=None,
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
    """按 ID 来源查询：`demo:` 只查演示目录，`amap:` 只查高德，互不回退。"""
    query_center = GeoLocation(lat=lat, lng=lng)
    if place_id.startswith("amap:"):
        return _amap_place_detail(place_id[len("amap:") :], query_center)
    if not place_id.startswith("demo:"):
        raise _place_not_found()
    key = place_id[len("demo:") :]
    seed = next((item for item in DEMO_PLACE_SEEDS if item.key == key), None)
    if seed is None:
        raise _place_not_found()
    return _to_place(seed, _seed_location(seed, get_demo_center()), query_center)


def _amap_place_detail(poi_id: str, query_center: GeoLocation) -> Place:
    """高德地点详情：未配置 503、超时 504、失败 502、不存在 404。"""
    if not _amap_api_key():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "高德服务未配置，暂不能查询真实地点详情",
                "retryable": False,
            },
        )
    try:
        poi = _amap_client().get_detail(poi_id)
    except AMapTimeout as exc:
        logger.warning("高德地点详情超时：%s", exc)
        raise HTTPException(
            status_code=504,
            detail={
                "code": "UPSTREAM_TIMEOUT",
                "message": "高德服务响应超时",
                "retryable": True,
            },
        ) from exc
    except AMapUnavailable as exc:
        logger.warning("高德地点详情失败：%s", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "UPSTREAM_ERROR",
                "message": "高德服务暂时不可用",
                "retryable": True,
            },
        ) from exc
    if poi is None:
        raise _place_not_found()
    return _amap_to_place(poi, _category_from_amap_type(poi.type_name), query_center)


def resolve_address(address: str) -> AddressResolveResponse:
    """手动地址解析（P1-10）：地址文本 → WGS84 候选。

    按契约不做演示回退：未配置高德返回 503，上游失败/超时返回
    502/504，无匹配返回 404；不根据字符串猜测坐标。地址与坐标仅用于
    本次请求，不写入日志或业务数据库，因此本函数与适配器日志均不含
    地址内容。
    """
    if not _amap_api_key():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "高德服务未配置，暂不能解析地址，可使用演示区域浏览示例数据",
                "retryable": False,
            },
        )
    try:
        matches = _amap_client().geocode(address)
    except AMapTimeout as exc:
        logger.warning("地址解析高德超时：%s", exc)
        raise HTTPException(
            status_code=504,
            detail={
                "code": "UPSTREAM_TIMEOUT",
                "message": "高德服务响应超时",
                "retryable": True,
            },
        ) from exc
    except AMapUnavailable as exc:
        logger.warning("地址解析高德失败：%s", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "UPSTREAM_ERROR",
                "message": "高德服务暂时不可用",
                "retryable": True,
            },
        ) from exc
    if not matches:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ADDRESS_NOT_FOUND",
                "message": "未找到匹配的地址，请尝试输入更完整的地址",
                "retryable": False,
            },
        )
    return AddressResolveResponse(
        matches=[
            AddressMatch(
                formatted_address=match.formatted_address,
                location=GeoLocation(lat=match.lat, lng=match.lng),
                data_source="amap",
            )
            for match in matches
        ]
    )


class BoundNearbyService:
    """Expose nearby queries for Agent tools (stateless; no database session)."""

    def search_nearby(
        self,
        *,
        lat: float,
        lng: float,
        category: NearbyCategory,
        radius_m: int,
        center_source: RequestCenterSource,
    ) -> NearbyResponse:
        return search_nearby(
            lat=lat,
            lng=lng,
            category=category,
            radius_m=radius_m,
            center_source=center_source,
        )
