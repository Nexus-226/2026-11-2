"""P1-9 高德接入测试：全部使用 MockTransport 模拟响应，不访问真实高德。"""

import logging
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db, init_db
from app.main import app
from app.services import nearby_service
from app.services.amap import (
    AMapClient,
    AMapUnavailable,
    _parse_geocodes,
    gcj02_to_wgs84,
    wgs84_to_gcj02,
)

TEST_KEY = "test-amap-key"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)
    monkeypatch.delenv("PET_AGENT_DEMO_CENTER_LAT", raising=False)
    monkeypatch.delenv("PET_AGENT_DEMO_CENTER_LNG", raising=False)
    database_url = URL.create("sqlite", database=str(tmp_path / "amap.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
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


def set_amap_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", TEST_KEY)


def patch_client(
    monkeypatch: pytest.MonkeyPatch, transport: httpx.BaseTransport
) -> None:
    monkeypatch.setattr(
        nearby_service,
        "_amap_client",
        lambda: AMapClient(api_key=TEST_KEY, transport=transport),
    )


def poi(
    poi_id: str,
    name: str,
    *,
    gcj_lat: float,
    gcj_lng: float,
    type_name: str = "医疗保健服务;动物医疗场所;宠物医院",
    tel: str | None = None,
    address: str = "示例路 18 号",
) -> dict[str, object]:
    body: dict[str, object] = {
        "id": poi_id,
        "name": name,
        "location": f"{gcj_lng},{gcj_lat}",
        "type": type_name,
        "address": address,
    }
    if tel is not None:
        body["business"] = {"tel": tel}
    return body


def ok_body(pois: list[dict[str, object]]) -> dict[str, object]:
    return {"status": "1", "info": "OK", "infocode": "10000", "pois": pois}


def around_transport(
    requests: list[httpx.Request], pois: list[dict[str, object]]
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=ok_body(pois))

    return httpx.MockTransport(handler)


def detail_transport(pois: list[dict[str, object]]) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, json=ok_body(pois)))


def failed_body() -> dict[str, object]:
    return {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}


def test_nearby_uses_amap_results_and_converts_coordinates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    requests: list[httpx.Request] = []
    pois = [
        poi(
            "B0AAA1",
            "安心宠物医院",
            gcj_lat=39.9045,
            gcj_lng=116.4050,
            tel="010-1234-5678",
        ),
        poi("B0BBB2", "示例路宠物诊所", gcj_lat=39.9090, gcj_lng=116.4094),
    ]
    patch_client(monkeypatch, around_transport(requests, pois))
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amap"
    assert body["fallback_reason"] is None
    assert body["search_center"] == {
        "location": {"lat": 39.9001, "lng": 116.4001},
        "source": "user_location",
        "label": "当前位置",
    }
    # 请求把 WGS84 中心转为 GCJ-02：坐标参数与原始输入不同但偏差有限。
    assert len(requests) == 1
    params = requests[0].url.params
    assert params["key"] == TEST_KEY
    assert params["keywords"] == "宠物医院|动物医院"
    assert params["radius"] == "3000"
    assert params["show_fields"] == "business"
    assert params["page_size"] == "25"
    gcj_lng, gcj_lat = (float(value) for value in params["location"].split(","))
    assert 0.0005 <= gcj_lat - 39.9001 <= 0.02
    assert 0.0005 <= gcj_lng - 116.4001 <= 0.02
    places = body["places"]
    assert [item["id"] for item in places] == ["amap:B0AAA1", "amap:B0BBB2"]
    first = places[0]
    assert first["data_source"] == "amap"
    assert first["category"] == "pet_hospital"
    assert first["name"] == "安心宠物医院"
    assert first["phone"] == "010-1234-5678"
    assert first["address"] == "示例路 18 号"
    assert first["business_status"] == "unknown"
    assert first["navigation_url"] is None
    assert isinstance(first["distance_m"], int)
    # 响应坐标已转回 WGS84：与高德原始 GCJ-02 不同，且偏差有限。
    assert 1e-6 < abs(first["location"]["lat"] - 39.9045) < 0.02
    assert 1e-6 < abs(first["location"]["lng"] - 116.4050) < 0.02


def test_nearby_dedupes_by_amap_id_and_filters_by_radius(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    requests: list[httpx.Request] = []
    pois = [
        poi("B0AAA1", "安心宠物医院", gcj_lat=39.9045, gcj_lng=116.4050),
        poi("B0AAA1", "重复推送的同一地点", gcj_lat=39.9050, gcj_lng=116.4060),
        poi("B0CCC3", "远处的宠物医院", gcj_lat=40.0100, gcj_lng=116.5100),
    ]
    patch_client(monkeypatch, around_transport(requests, pois))
    response = client.get(
        "/api/v1/nearby",
        params={
            "lat": 39.9001,
            "lng": 116.4001,
            "type": "pet_hospital",
            "radius_m": 3000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amap"
    assert body["fallback_reason"] is None
    assert [item["id"] for item in body["places"]] == ["amap:B0AAA1"]


@pytest.mark.parametrize(
    ("category", "expected_keywords"),
    [
        ("pet_hospital", "宠物医院|动物医院"),
        ("pet_grooming", "宠物美容|宠物SPA|宠物洗护"),
        ("pet_store", "宠物用品|宠物店"),
    ],
)
def test_nearby_sends_category_keywords(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    expected_keywords: str,
) -> None:
    set_amap_key(monkeypatch)
    requests: list[httpx.Request] = []
    patch_client(monkeypatch, around_transport(requests, []))
    response = client.get(
        "/api/v1/nearby", params={"lat": 39.9001, "lng": 116.4001, "type": category}
    )
    assert response.status_code == 200
    assert requests[0].url.params["keywords"] == expected_keywords


def test_amap_empty_result_is_not_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    patch_client(monkeypatch, around_transport([], []))
    response = client.get(
        "/api/v1/nearby", params={"lat": 39.9001, "lng": 116.4001, "type": "pet_store"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amap"
    assert body["fallback_reason"] is None
    assert body["places"] == []


def test_nearby_falls_back_to_demo_when_amap_reports_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    patch_client(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=failed_body())),
    )
    response = client.get(
        "/api/v1/nearby",
        params={
            "lat": 31.2304,
            "lng": 121.4737,
            "type": "pet_grooming",
            "center_source": "resolved_address",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "amap_unavailable"
    # 回落沿用原查询中心与来源，不切换到演示中心。
    assert body["search_center"]["location"] == {"lat": 31.2304, "lng": 121.4737}
    assert body["search_center"]["source"] == "resolved_address"
    assert body["search_center"]["label"] == "所选地址"
    for place in body["places"]:
        assert place["id"].startswith("demo:")
        assert place["data_source"] == "demo"


@pytest.mark.parametrize(
    "transport",
    [
        httpx.MockTransport(lambda request: httpx.Response(500)),
        httpx.MockTransport(lambda request: httpx.Response(200, content=b"<html>")),
    ],
)
def test_nearby_falls_back_on_http_and_parse_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    transport: httpx.MockTransport,
) -> None:
    set_amap_key(monkeypatch)
    patch_client(monkeypatch, transport)
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "amap_unavailable"


def test_nearby_falls_back_on_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("模拟连接超时")

    patch_client(monkeypatch, httpx.MockTransport(handler))
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "amap_unavailable"


def test_amap_failure_does_not_leak_key_in_logs_or_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "super-secret-key")
    patch_client(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=failed_body())),
    )
    with caplog.at_level(logging.WARNING):
        response = client.get(
            "/api/v1/nearby",
            params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
        )
    assert response.status_code == 200
    assert "super-secret-key" not in caplog.text
    assert "super-secret-key" not in response.text


def test_place_detail_amap_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    poi_body = poi(
        "B0AAA1",
        "安心宠物医院",
        gcj_lat=39.9045,
        gcj_lng=116.4050,
        tel="010-1234-5678",
    )
    patch_client(monkeypatch, detail_transport([poi_body]))
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 200
    place = response.json()
    assert place["id"] == "amap:B0AAA1"
    assert place["data_source"] == "amap"
    assert place["category"] == "pet_hospital"
    assert place["phone"] == "010-1234-5678"
    assert isinstance(place["distance_m"], int)
    assert place["distance_m"] >= 0
    assert place["navigation_url"] is None


@pytest.mark.parametrize(
    ("type_name", "expected_category"),
    [
        ("医疗保健服务;动物医疗场所;宠物医院", "pet_hospital"),
        ("生活服务;宠物服务;宠物美容", "pet_grooming"),
        ("购物服务;商场;超市;宠物用品店", "pet_store"),
        ("购物服务;其他未知分类", "pet_store"),
    ],
)
def test_place_detail_maps_category_from_amap_type(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    type_name: str,
    expected_category: str,
) -> None:
    set_amap_key(monkeypatch)
    poi_body = poi(
        "B0CCC3", "某宠物场所", gcj_lat=39.9045, gcj_lng=116.4050, type_name=type_name
    )
    patch_client(monkeypatch, detail_transport([poi_body]))
    response = client.get(
        "/api/v1/places/amap:B0CCC3", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 200
    assert response.json()["category"] == expected_category


def test_place_detail_amap_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    patch_client(monkeypatch, detail_transport([]))
    response = client.get(
        "/api/v1/places/amap:B0MISS", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLACE_NOT_FOUND"


def test_place_detail_amap_reports_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    patch_client(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=failed_body())),
    )
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    # 失败时绝不静默替换为演示地点。
    assert "places" not in response.json()


def test_place_detail_amap_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("模拟读取超时")

    patch_client(monkeypatch, httpx.MockTransport(handler))
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_place_detail_amap_not_configured(client: TestClient) -> None:
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_nearby_skips_pois_with_invalid_coordinates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_amap_key(monkeypatch)
    pois = [
        poi("B0NAN", "坐标异常医院", gcj_lat=float("nan"), gcj_lng=float("nan")),
        poi("B0INF", "无穷医院", gcj_lat=float("inf"), gcj_lng=float("inf")),
        poi("B0OOR", "越界医院", gcj_lat=999.0, gcj_lng=999.0),
        poi("B0OK", "正常医院", gcj_lat=39.9045, gcj_lng=116.4050),
    ]
    patch_client(monkeypatch, around_transport([], pois))
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amap"
    assert [place["id"] for place in body["places"]] == ["amap:B0OK"]


@pytest.mark.parametrize(
    ("wgs", "gcj"),
    [
        ((39.911954, 116.377817), (39.913345, 116.384047)),  # 北京
        ((31.1774276, 121.5272106), (31.175304, 121.531542)),  # 上海
        ((22.543847, 113.912316), (22.540796, 113.917176)),  # 深圳
    ],
)
def test_wgs84_to_gcj02_matches_reference_vectors(
    wgs: tuple[float, float], gcj: tuple[float, float]
) -> None:
    # 期望值取自 eviltransform 公开测试向量（保留 6 位小数）。
    result = wgs84_to_gcj02(*wgs)
    assert abs(result[0] - gcj[0]) <= 1e-6
    assert abs(result[1] - gcj[1]) <= 1e-6


def test_gcj02_conversion_round_trips_in_china() -> None:
    wgs = (39.9001, 116.4001)
    gcj_lat, gcj_lng = wgs84_to_gcj02(*wgs)
    # 北京城区内偏移应明显大于精度要求，且可稳定反演回原坐标。
    assert abs(gcj_lat - wgs[0]) > 1e-4
    assert abs(gcj_lng - wgs[1]) > 1e-4
    back_lat, back_lng = gcj02_to_wgs84(gcj_lat, gcj_lng)
    assert abs(back_lat - wgs[0]) <= 2e-5
    assert abs(back_lng - wgs[1]) <= 2e-5


def test_conversion_is_identity_outside_china() -> None:
    assert wgs84_to_gcj02(-33.87, 151.21) == (-33.87, 151.21)
    assert gcj02_to_wgs84(40.7128, -74.006) == (40.7128, -74.006)


def geocode_item(
    formatted_address: str, *, gcj_lat: float, gcj_lng: float
) -> dict[str, object]:
    return {"formatted_address": formatted_address, "location": f"{gcj_lng},{gcj_lat}"}


def test_parse_geocodes_missing_or_nonarray_raises_unavailable() -> None:
    """status=1 但 geocodes 缺失/非数组属于上游结构异常（→502），不是无匹配（→404）。"""
    with pytest.raises(AMapUnavailable):
        _parse_geocodes({"status": "1", "info": "OK", "infocode": "10000"})
    with pytest.raises(AMapUnavailable):
        _parse_geocodes({"status": "1", "geocodes": "nodata"})
    with pytest.raises(AMapUnavailable):
        _parse_geocodes({"status": "1", "geocodes": {"0": {}}})


def test_parse_geocodes_empty_list_is_no_match() -> None:
    """合法的空 geocodes 数组表示无匹配，由上层映射 404。"""
    assert _parse_geocodes({"status": "1", "info": "OK", "geocodes": []}) == []


def test_parse_geocodes_filters_nan_inf_and_out_of_range_coordinates() -> None:
    payload = {
        "status": "1",
        "geocodes": [
            geocode_item("非有限纬度", gcj_lat=float("nan"), gcj_lng=116.4050),
            geocode_item("非有限经度", gcj_lat=39.9045, gcj_lng=float("inf")),
            geocode_item("越界纬度", gcj_lat=999.0, gcj_lng=116.4050),
            geocode_item("越界经度", gcj_lat=39.9045, gcj_lng=-1000.0),
            geocode_item("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050),
        ],
    }
    matches = _parse_geocodes(payload)
    assert [match.formatted_address for match in matches] == [
        "北京市朝阳区示例路 18 号"
    ]
    assert -90.0 <= matches[0].lat <= 90.0
    assert -180.0 <= matches[0].lng <= 180.0


def track_client_close(
    monkeypatch: pytest.MonkeyPatch, transport: httpx.BaseTransport
) -> list[bool]:
    """记录 AMapClient.close 调用；请求路径仍走 nearby_service._amap_client。"""
    closed: list[bool] = []
    original_close = AMapClient.close

    def tracking_close(instance: AMapClient) -> None:
        closed.append(True)
        original_close(instance)

    monkeypatch.setattr(AMapClient, "close", tracking_close)
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", TEST_KEY)
    patch_client(monkeypatch, transport)
    return closed


def test_amap_client_closes_after_nearby_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = track_client_close(
        monkeypatch,
        around_transport(
            [], [poi("B0AAA1", "安心宠物医院", gcj_lat=39.9050, gcj_lng=116.4060)]
        ),
    )
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "amap"
    assert closed == [True]


def test_amap_client_closes_after_nearby_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = track_client_close(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=failed_body())),
    )
    response = client.get(
        "/api/v1/nearby",
        params={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
    )
    # 搜索失败按契约回落演示数据并标注来源，但连接池仍须关闭。
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert body["fallback_reason"] == "amap_unavailable"
    assert closed == [True]


def test_amap_client_closes_after_detail_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = track_client_close(
        monkeypatch,
        detail_transport(
            [poi("B0AAA1", "安心宠物医院", gcj_lat=39.9050, gcj_lng=116.4060)]
        ),
    )
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 200
    assert closed == [True]


def test_amap_client_closes_after_detail_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = track_client_close(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=failed_body())),
    )
    response = client.get(
        "/api/v1/places/amap:B0AAA1", params={"lat": 39.9001, "lng": 116.4001}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert closed == [True]
