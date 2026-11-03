"""地点详情路由（P1-8 演示数据版；P1-9 支持 `amap:` 前缀查询高德）。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.nearby import Place
from app.services import nearby_service

router = APIRouter()


@router.get("/{place_id}", response_model=Place)
def get_place(
    place_id: str,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
) -> Place:
    """地点详情；distance_m 依赖查询中心，必须附带 lat、lng。"""
    return nearby_service.get_place(place_id, lat=lat, lng=lng)
