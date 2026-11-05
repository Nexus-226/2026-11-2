"""P1-11 附近搜索只读工具的边界测试。

工具只声明输入 Schema 并通过 Service 查询；空结果返回 NearbyResponse.places == []，
失败由 Service 抛出可识别异常并映射为 error，不把失败伪装成空结果。
"""

from uuid import UUID

from app.agent.errors import DomainError
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ToolCallRequest
from app.agent.tools import build_default_registry
from app.schemas.nearby import NearbyResponse, Place
from app.schemas.pet import PetRead


class FakePetService:
    """仅用于满足 build_default_registry 的 PetService 参数。"""

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return None

    def list_pets(self) -> list[PetRead]:
        return []


def _place(**overrides: object) -> Place:
    base: dict[str, object] = {
        "id": "demo:pet-hospital-01",
        "name": "安心宠物医院（示例）",
        "category": "pet_hospital",
        "address": "演示区幸福路 1 号",
        "phone": "010-0000-0001",
        "location": {"lat": 39.9041, "lng": 116.4021},
        "distance_m": 860,
        "business_status": "open",
        "business_hours_today": None,
        "navigation_url": None,
        "data_source": "demo",
    }
    base.update(overrides)
    return Place(**base)


def _response(**overrides: object) -> NearbyResponse:
    base: dict[str, object] = {
        "places": [_place()],
        "search_center": {
            "location": {"lat": 39.9001, "lng": 116.4001},
            "source": "user_location",
            "label": "当前位置",
        },
        "source": "demo",
        "fallback_reason": "amap_not_configured",
    }
    base.update(overrides)
    return NearbyResponse(**base)


class FakeNearbyService:
    """记录最后一次调用的参数，返回预设结果。"""

    def __init__(self, response: NearbyResponse | None = None) -> None:
        self._response = response if response is not None else _response()
        self.last_args: dict[str, object] = {}

    def search_nearby(self, **kwargs: object) -> NearbyResponse:
        self.last_args = kwargs
        return self._response


class FailingNearbyService:
    def search_nearby(self, **kwargs: object) -> NearbyResponse:
        raise DomainError("UPSTREAM_ERROR", "附近服务暂不可用")


def _runtime(nearby_service: object = FakeNearbyService()) -> AgentRuntime:
    registry = build_default_registry(FakePetService(), nearby_service=nearby_service)
    return AgentRuntime(registry)


def _call(runtime: AgentRuntime, **args: object):
    return runtime.run_tools(
        [ToolCallRequest(name="search_nearby_pet_services", args=dict(args))]
    )[0]


def test_search_nearby_returns_response() -> None:
    result = _call(
        _runtime(), lat=39.9001, lng=116.4001, type="pet_hospital", radius_m=3000
    )
    assert result.status == "success"
    assert isinstance(result.data, NearbyResponse)
    assert result.data.places[0].category == "pet_hospital"
    assert result.data.source == "demo"


def test_search_nearby_defaults_radius_and_center_source() -> None:
    service = FakeNearbyService()
    result = _call(_runtime(service), lat=39.9001, lng=116.4001, type="pet_store")
    assert result.status == "success"
    assert service.last_args["radius_m"] == 3000
    assert service.last_args["center_source"] == "user_location"
    assert service.last_args["category"] == "pet_store"


def test_search_nearby_passes_center_source_through() -> None:
    service = FakeNearbyService()
    result = _call(
        _runtime(service),
        lat=39.9001,
        lng=116.4001,
        type="pet_grooming",
        center_source="resolved_address",
    )
    assert result.status == "success"
    assert service.last_args["center_source"] == "resolved_address"
    assert service.last_args["lat"] == 39.9001
    assert service.last_args["lng"] == 116.4001


def test_search_nearby_empty_places_is_success() -> None:
    empty = _response(places=[])
    result = _call(
        _runtime(FakeNearbyService(empty)),
        lat=39.9001,
        lng=116.4001,
        type="pet_hospital",
    )
    assert result.status == "success"
    assert result.data.places == []


def test_search_nearby_failure_is_error_not_empty() -> None:
    result = _call(
        _runtime(FailingNearbyService()),
        lat=39.9001,
        lng=116.4001,
        type="pet_hospital",
    )
    assert result.status == "error"
    assert result.error_code == "UPSTREAM_ERROR"


def test_invalid_type_is_validation_error() -> None:
    result = _call(_runtime(), lat=39.9001, lng=116.4001, type="unknown")
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_invalid_radius_is_validation_error() -> None:
    result = _call(
        _runtime(), lat=39.9001, lng=116.4001, type="pet_hospital", radius_m=10
    )
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_invalid_coordinates_are_validation_error() -> None:
    result = _call(_runtime(), lat=91.0, lng=116.4001, type="pet_hospital")
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_demo_region_is_invalid_center_source_for_tool() -> None:
    result = _call(
        _runtime(),
        lat=39.9001,
        lng=116.4001,
        type="pet_hospital",
        center_source="demo_region",
    )
    assert result.status == "error"
    assert result.error_code == "VALIDATION_ERROR"


def test_nearby_tool_absent_without_service() -> None:
    registry = build_default_registry(FakePetService())
    assert "search_nearby_pet_services" not in registry.names()


def test_nearby_tool_description_limits_demo_fallback_and_navigation() -> None:
    registry = build_default_registry(
        FakePetService(), nearby_service=FakeNearbyService()
    )
    description = registry.get("search_nearby_pet_services").description
    assert "不得据此判断真实附近有没有服务" in description
    assert "不要建议用户重新定位" in description
    assert "启用导航" in description
