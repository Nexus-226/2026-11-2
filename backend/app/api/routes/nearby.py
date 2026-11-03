"""附近服务查询路由（P1-8 演示数据版）。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.schemas.nearby import NearbyCategory, NearbyResponse
from app.services import nearby_service

router = APIRouter()


@router.get("", response_model=NearbyResponse)
def search_nearby(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    type: NearbyCategory,
    radius_m: Annotated[int, Query(ge=1000, le=20000)] = 3000,
    center_source: Literal["user_location", "resolved_address"] = "user_location",
) -> NearbyResponse:
    """附近查询；高德接入前按契约回退演示数据并标注来源。"""
    return nearby_service.search_nearby(
        lat=lat,
        lng=lng,
        category=type,
        radius_m=radius_m,
        center_source=center_source,
    )


@router.get("/demo", response_model=NearbyResponse)
def search_demo_region(
    type: NearbyCategory,
    radius_m: Annotated[int, Query(ge=1000, le=20000)] = 3000,
) -> NearbyResponse:
    """用户主动选择的演示区域入口，使用配置的演示中心，不接入定位。"""
    return nearby_service.search_demo_region(category=type, radius_m=radius_m)
