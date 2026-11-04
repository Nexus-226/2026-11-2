"""手动地址解析路由（P1-10）：拒绝定位后由用户主动输入地址的回退。"""

from fastapi import APIRouter

from app.schemas.nearby import AddressResolveRequest, AddressResolveResponse
from app.services import nearby_service

router = APIRouter()


@router.post("/resolve", response_model=AddressResolveResponse)
def resolve_address(payload: AddressResolveRequest) -> AddressResolveResponse:
    """把地址解析为候选（地标 POI + geocode）；由用户选择，不自动选取。"""
    return nearby_service.resolve_address(payload.address, payload.city)
