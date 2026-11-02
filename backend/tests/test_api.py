from app.agent.runtime import AgentRuntime
from app.agent.tools import build_tool_allowlist
from app.main import app, health
from app.schemas import ChatRequest, NearbyQuery, PetCreate, PetUpdate
from app.services.nearby_service import NearbyService
from app.services.pet_service import PetService


def test_health_openapi_and_seed_pet() -> None:
    assert health()["status"] == "ok"
    schema = app.openapi()
    assert "/api/v1/chat" in schema["paths"]
    assert "/api/v1/pets/{pet_id}" in schema["paths"]
    assert PetService().get("demo-user", "pet-demo-001") is not None


def test_pet_crud_service_boundary() -> None:
    pets = PetService()
    created = pets.create(PetCreate(user_id="demo-user", name="豆包", species="dog", age_years=2))
    updated = pets.update(created.id, PetUpdate(user_id="demo-user", health_notes="对鸡肉敏感"))
    assert updated and updated.health_notes == "对鸡肉敏感"
    assert pets.delete("demo-user", created.id) is True
    assert pets.get("demo-user", created.id) is None


def test_chat_uses_pet_tool_and_adds_medical_disclaimer() -> None:
    pets = PetService()
    runtime = AgentRuntime(build_tool_allowlist(pets))
    response = runtime.chat(ChatRequest(user_id="demo-user", pet_id="pet-demo-001", message="团子不吃东西，是不是生病了？"), request_id="req_test")
    assert response.tool_results[0].status == "success"
    assert "专业兽医" in response.reply


def test_nearby_coordinate_boundary_and_manual_fallback() -> None:
    service = NearbyService()
    outside = service.search(NearbyQuery(lat=51.5074, lng=-0.1278))
    assert outside.coordinate_converted is False
    manual = service.search(NearbyQuery(address="上海市人民广场"))
    assert manual.location_source == "manual_address_mock"
    assert manual.coordinate_converted is True
