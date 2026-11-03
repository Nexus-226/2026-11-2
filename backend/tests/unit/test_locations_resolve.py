"""P1-10 手动地址解析测试：全部使用 MockTransport 模拟响应，不访问真实高德。"""

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
from app.services.amap import AMapClient

TEST_KEY = "test-amap-key"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)
    database_url = URL.create("sqlite", database=str(tmp_path / "resolve.db"))
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


def patch_client(
    monkeypatch: pytest.MonkeyPatch, transport: httpx.BaseTransport
) -> None:
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", TEST_KEY)
    monkeypatch.setattr(
        nearby_service,
        "_amap_client",
        lambda: AMapClient(api_key=TEST_KEY, transport=transport),
    )


def geocode(
    formatted_address: str, *, gcj_lat: float, gcj_lng: float
) -> dict[str, object]:
    """构造高德地理编码候选；故意包含厂商附加字段以验证不被透出。"""
    return {
        "formatted_address": formatted_address,
        "location": f"{gcj_lng},{gcj_lat}",
        "level": "门址",
        "country": "中国",
        "province": "北京市",
        "city": "北京市",
        "district": "朝阳区",
        "street": "示例路",
        "number": "18号",
        "adcode": "110105",
    }


def ok_body(geocodes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": str(len(geocodes)),
        "geocodes": geocodes,
    }


def geocode_transport(
    requests: list[httpx.Request],
    payload: dict[str, object] | Exception,
    *,
    status_code: int = 200,
    text: str | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if isinstance(payload, Exception):
            raise payload
        if text is not None:
            return httpx.Response(status_code, text=text)
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


def resolve(client: TestClient, address: str = "北京市朝阳区示例路 18 号"):
    return client.post("/api/v1/locations/resolve", json={"address": address})


def test_resolve_returns_matches_with_wgs84_coordinates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests,
            ok_body(
                [geocode("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050)]
            ),
        ),
    )
    response = resolve(client)
    assert response.status_code == 200
    body = response.json()
    assert len(body["matches"]) == 1
    match = body["matches"][0]
    assert set(match.keys()) == {"formatted_address", "location", "data_source"}
    assert match["formatted_address"] == "北京市朝阳区示例路 18 号"
    assert match["data_source"] == "amap"
    # 响应坐标为 WGS84：与请求中的 GCJ-02 输入不同且偏差有限。
    assert match["location"]["lat"] != 39.9045
    assert match["location"]["lng"] != 116.4050
    assert abs(match["location"]["lat"] - 39.9045) < 0.05
    assert abs(match["location"]["lng"] - 116.4050) < 0.05
    # 不透出厂商原始字段。
    assert "geocodes" not in body and "status" not in body and "count" not in body


def test_resolve_posts_geocode_request_with_stripped_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests, ok_body([geocode("x", gcj_lat=39.9, gcj_lng=116.4)])
        ),
    )
    response = resolve(client, "  北京市朝阳区示例路 18 号  ")
    assert response.status_code == 200
    request = requests[0]
    assert request.url.path == "/v3/geocode/geo"
    params = dict(request.url.params)
    assert params["key"] == TEST_KEY
    assert params["address"] == "北京市朝阳区示例路 18 号"


def test_resolve_returns_all_candidates_in_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests,
            ok_body(
                [
                    geocode(
                        "北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050
                    ),
                    geocode("北京市海淀区示例路 18 号", gcj_lat=39.96, gcj_lng=116.31),
                    geocode("北京市东城区示例路 18 号", gcj_lat=39.92, gcj_lng=116.41),
                ]
            ),
        ),
    )
    body = resolve(client).json()
    addresses = [match["formatted_address"] for match in body["matches"]]
    # 多条候选全部返回且保持顺序，不自动选择第一条。
    assert addresses == [
        "北京市朝阳区示例路 18 号",
        "北京市海淀区示例路 18 号",
        "北京市东城区示例路 18 号",
    ]


def test_resolve_skips_entries_without_valid_location_or_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests,
            ok_body(
                [
                    {"formatted_address": "缺坐标的候选"},
                    {"location": "116.4,39.9"},
                    {"formatted_address": "  ", "location": "116.4,39.9"},
                    {"formatted_address": "坏坐标", "location": "not-a-point"},
                    geocode(
                        "北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050
                    ),
                ]
            ),
        ),
    )
    body = resolve(client).json()
    assert [match["formatted_address"] for match in body["matches"]] == [
        "北京市朝阳区示例路 18 号"
    ]


def test_resolve_no_match_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(monkeypatch, geocode_transport(requests, ok_body([])))
    response = resolve(client, "不存在的地址占位符")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "ADDRESS_NOT_FOUND"
    assert error["retryable"] is False


def test_resolve_failed_status_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests,
            {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"},
        ),
    )
    response = resolve(client)
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_ERROR"
    assert error["retryable"] is True


def test_resolve_http_error_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(requests, {"info": "error"}, status_code=500),
    )
    response = resolve(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_resolve_unparseable_body_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(requests, {}, text="<html>gateway error</html>"),
    )
    response = resolve(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_resolve_timeout_returns_504(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(requests, httpx.ConnectTimeout("timed out")),
    )
    response = resolve(client)
    assert response.status_code == 504
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_TIMEOUT"
    assert error["retryable"] is True


def test_resolve_without_key_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)

    def unexpected_client() -> object:
        raise AssertionError("未配置密钥时不应创建高德客户端")

    monkeypatch.setattr(nearby_service, "_amap_client", unexpected_client)
    response = resolve(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.parametrize(
    "payload",
    [
        {"address": "   "},
        {"address": ""},
        {"address": "a" * 201},
        {},
        {"address": 123},
    ],
)
def test_resolve_rejects_invalid_input(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> None:
    def unexpected_client() -> object:
        raise AssertionError("输入校验失败时不应调用高德")

    monkeypatch.setattr(nearby_service, "_amap_client", unexpected_client)
    response = client.post("/api/v1/locations/resolve", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_resolve_accepts_200_char_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests, ok_body([geocode("x", gcj_lat=39.9, gcj_lng=116.4)])
        ),
    )
    response = resolve(client, "a" * 200)
    assert response.status_code == 200


def test_resolve_never_logs_address_or_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        geocode_transport(
            requests, {"status": "0", "info": "error", "infocode": "10001"}
        ),
    )
    with caplog.at_level(logging.DEBUG):
        response = resolve(client, "用户的私密地址文本")
    assert response.status_code == 502
    assert "用户的私密地址文本" not in caplog.text
    assert TEST_KEY not in caplog.text
