import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db, init_db
from app.main import app

PLACE_FIELDS = {
    "id",
    "name",
    "category",
    "address",
    "phone",
    "location",
    "distance_m",
    "business_status",
    "navigation_url",
    "data_source",
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("PET_AGENT_DEMO_CENTER_LAT", raising=False)
    monkeypatch.delenv("PET_AGENT_DEMO_CENTER_LNG", raising=False)
    database_url = URL.create("sqlite", database=str(tmp_path / "nearby.db"))
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    init_db(database_url.render_as_string(hide_password=False))
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    monkeypatch.setattr("app.main.init_db", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def get_places(body: dict[str, object]) -> list[dict[str, object]]:
    places = body["places"]
    assert isinstance(places, list)
    return places


def test_demo_region_returns_demo_places_sorted_by_distance(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/nearby/demo", params={"type": "pet_hospital", "radius_m": 20000}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] is None
    assert body["search_center"]["source"] == "demo_region"
    assert body["search_center"]["label"] == "演示区域（非实时位置）"
    assert body["search_center"]["location"] == {"lat": 39.9001, "lng": 116.4001}
    places = get_places(body)
    assert len(places) == 3
    distances = [place["distance_m"] for place in places]
    assert distances == sorted(distances)
    for place in places:
        assert set(place) == PLACE_FIELDS
        assert place["id"].startswith("demo:")
        assert place["data_source"] == "demo"
        assert place["category"] == "pet_hospital"
        assert place["navigation_url"] is None
        assert place["business_status"] in {"open", "closed", "unknown"}
        assert place["distance_m"] >= 0


def test_demo_region_filters_by_radius_and_returns_empty_list(
    client: TestClient,
) -> None:
    within = client.get(
        "/api/v1/nearby/demo", params={"type": "pet_hospital", "radius_m": 1000}
    )
    assert within.status_code == 200
    places = get_places(within.json())
    assert len(places) == 1
    assert places[0]["id"] == "demo:pet-hospital-01"
    assert 400 <= places[0]["distance_m"] <= 550

    empty = client.get(
        "/api/v1/nearby/demo", params={"type": "pet_store", "radius_m": 1000}
    )
    assert empty.status_code == 200
    assert get_places(empty.json()) == []


def test_demo_region_orders_ties_stably_by_id(client: TestClient) -> None:
    body = client.get(
        "/api/v1/nearby/demo", params={"type": "pet_grooming", "radius_m": 20000}
    ).json()
    places = get_places(body)
    pairs = [(place["distance_m"], place["id"]) for place in places]
    assert pairs == sorted(pairs)


def test_nearby_falls_back_to_demo_and_keeps_request_center(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "amap_not_configured"
    assert body["search_center"]["source"] == "user_location"
    assert body["search_center"]["label"] == "当前位置"
    assert body["search_center"]["location"] == {"lat": 39.9001, "lng": 116.4001}
    places = get_places(body)
    assert [place["id"] for place in places] == [
        "demo:pet-hospital-01",
        "demo:pet-hospital-02",
    ]


def test_nearby_uses_original_center_for_distance(client: TestClient) -> None:
    response = client.get(
        "/api/v1/nearby",
        params={
            "lat": 39.9201,
            "lng": 116.4001,
            "type": "pet_hospital",
            "radius_m": 20000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["search_center"]["location"] == {"lat": 39.9201, "lng": 116.4001}
    places = get_places(body)
    ids = [place["id"] for place in places]
    # 距离按请求中心计算而非演示中心：pet-hospital-02 反而比 -01 更近。
    assert ids == [
        "demo:pet-hospital-02",
        "demo:pet-hospital-01",
        "demo:pet-hospital-03",
    ]
    dlat = math.radians(39.9041 - 39.9201)
    dlng = math.radians(116.4021 - 116.4001)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(39.9201))
        * math.cos(math.radians(39.9041))
        * math.sin(dlng / 2) ** 2
    )
    expected = 2 * 6371008.8 * math.asin(math.sqrt(a))
    assert places[1]["distance_m"] == pytest.approx(expected, rel=0.01)


def test_nearby_passes_through_resolved_address_center(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/nearby",
        params={
            "lat": 39.9001,
            "lng": 116.4001,
            "type": "pet_grooming",
            "center_source": "resolved_address",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["search_center"]["source"] == "resolved_address"
    assert body["search_center"]["label"] == "所选地址"


def test_nearby_rejects_invalid_parameters(client: TestClient) -> None:
    base = {"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"}
    invalid_params = [
        {**base, "center_source": "demo_region"},
        {**base, "radius_m": 999},
        {**base, "radius_m": 20001},
        {**base, "type": "vet"},
        {**base, "lat": 91},
        {**base, "lng": -181},
        {"lng": 116.4001, "type": "pet_hospital"},
    ]
    for params in invalid_params:
        response = client.get("/api/v1/nearby", params=params)
        assert response.status_code == 422, params
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    for params in [
        {"type": "pet_hospital", "radius_m": 500},
        {"radius_m": 3000},
    ]:
        response = client.get("/api/v1/nearby/demo", params=params)
        assert response.status_code == 422, params

    # 演示入口不接受 center_source：即使传入也固定返回 demo_region。
    ignored = client.get(
        "/api/v1/nearby/demo",
        params={"type": "pet_hospital", "center_source": "user_location"},
    )
    assert ignored.status_code == 200
    assert ignored.json()["search_center"]["source"] == "demo_region"


def test_place_detail_uses_demo_catalog_and_query_center(
    client: TestClient,
) -> None:
    near = client.get(
        "/api/v1/places/demo:pet-hospital-01",
        params={"lat": 39.9001, "lng": 116.4001},
    )
    assert near.status_code == 200
    place = near.json()
    assert set(place) == PLACE_FIELDS
    assert place["id"] == "demo:pet-hospital-01"
    assert place["data_source"] == "demo"
    assert place["distance_m"] == pytest.approx(477, rel=0.15)

    far = client.get(
        "/api/v1/places/demo:pet-hospital-01",
        params={"lat": 40.0001, "lng": 116.4001},
    )
    assert far.status_code == 200
    assert far.json()["distance_m"] > place["distance_m"]


def test_place_detail_error_paths(client: TestClient) -> None:
    missing = client.get(
        "/api/v1/places/demo:does-not-exist",
        params={"lat": 39.9001, "lng": 116.4001},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PLACE_NOT_FOUND"

    unknown_prefix = client.get(
        "/api/v1/places/other:place", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert unknown_prefix.status_code == 404
    assert unknown_prefix.json()["error"]["code"] == "PLACE_NOT_FOUND"

    amap = client.get(
        "/api/v1/places/amap:B0FFFExample", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert amap.status_code == 503
    assert amap.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    no_center = client.get("/api/v1/places/demo:pet-hospital-01")
    assert no_center.status_code == 422
    assert no_center.json()["error"]["code"] == "VALIDATION_ERROR"


def test_demo_center_config_moves_seed_locations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PET_AGENT_DEMO_CENTER_LAT", "31.2304")
    monkeypatch.setenv("PET_AGENT_DEMO_CENTER_LNG", "121.4737")
    response = client.get("/api/v1/nearby/demo", params={"type": "pet_hospital"})
    assert response.status_code == 200
    body = response.json()
    assert body["search_center"]["location"] == {"lat": 31.2304, "lng": 121.4737}
    places = get_places(body)
    assert places[0]["location"] == {"lat": 31.2344, "lng": 121.4757}


def test_invalid_demo_center_config_falls_back_to_default(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PET_AGENT_DEMO_CENTER_LAT", "not-a-number")
    monkeypatch.setenv("PET_AGENT_DEMO_CENTER_LNG", "999")
    response = client.get("/api/v1/nearby/demo", params={"type": "pet_hospital"})
    assert response.status_code == 200
    body = response.json()
    assert body["search_center"]["location"] == {"lat": 39.9001, "lng": 116.4001}
