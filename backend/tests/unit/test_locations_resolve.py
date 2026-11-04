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
    formatted_address: str,
    *,
    gcj_lat: float,
    gcj_lng: float,
    level: object = "门址",
    city: object = "北京市",
    district: object = "朝阳区",
) -> dict[str, object]:
    """构造高德地理编码候选；故意包含厂商附加字段以验证不被透出。

    level/city/district 用 object 类型以模拟高德把无值字段返回为
    `[]` 的情况。
    """
    return {
        "formatted_address": formatted_address,
        "location": f"{gcj_lng},{gcj_lat}",
        "level": level,
        "country": "中国",
        "province": "北京市",
        "city": city,
        "district": district,
        "street": "示例路",
        "number": "18号",
        "adcode": "110105",
    }


def poi_item(
    poi_id: str,
    name: str,
    *,
    gcj_lat: float,
    gcj_lng: float,
    address: str = "人民大道185号",
    pname: str = "上海市",
    cityname: str = "上海市",
    adname: str = "黄浦区",
    type_name: str = "风景名胜;公园广场;城市广场",
) -> dict[str, object]:
    """构造 v5 place/text 地标 POI；字段形状按真实响应采样。"""
    return {
        "id": poi_id,
        "name": name,
        "location": f"{gcj_lng},{gcj_lat}",
        "type": type_name,
        "typecode": "110105",
        "pname": pname,
        "cityname": cityname,
        "adname": adname,
        "address": address,
        "parent": "",
        "distance": "",
    }


def ok_body(geocodes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": str(len(geocodes)),
        "geocodes": geocodes,
    }


def poi_ok_body(pois: list[dict[str, object]]) -> dict[str, object]:
    return {"status": "1", "info": "OK", "infocode": "10000", "pois": pois}


def amap_transport(
    requests: list[httpx.Request],
    *,
    geocode_payload: dict[str, object] | Exception | None = None,
    text_payload: dict[str, object] | Exception | None = None,
    status_code: int = 200,
    text: str | None = None,
) -> httpx.MockTransport:
    """按路径分发的双端点 MockTransport（P1-10 双查）。

    `/v3/geocode/geo` 返回 `geocode_payload`，`/v5/place/text` 返回
    `text_payload`，缺省均为“合法空候选”；`text` 覆盖为原始响应体
    （模拟无法解析的响应），`status_code` 作用于两个端点。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload: dict[str, object] | Exception
        if request.url.path == "/v3/geocode/geo":
            payload = geocode_payload if geocode_payload is not None else ok_body([])
        else:
            payload = text_payload if text_payload is not None else poi_ok_body([])
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
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [geocode("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050)]
            ),
        ),
    )
    response = resolve(client)
    assert response.status_code == 200
    body = response.json()
    assert len(body["matches"]) == 1
    match = body["matches"][0]
    assert set(match.keys()) == {
        "formatted_address",
        "name",
        "city",
        "district",
        "level",
        "match_kind",
        "location",
        "data_source",
    }
    assert match["formatted_address"] == "北京市朝阳区示例路 18 号"
    assert match["data_source"] == "amap"
    # geocode 候选：name 为 null，level 为高德级别原文，省市区来自高德。
    assert match["match_kind"] == "geocode"
    assert match["name"] is None
    assert match["city"] == "北京市"
    assert match["district"] == "朝阳区"
    assert match["level"] == "门址"
    # 响应坐标为 WGS84：与请求中的 GCJ-02 输入不同且偏差有限。
    assert match["location"]["lat"] != 39.9045
    assert match["location"]["lng"] != 116.4050
    assert abs(match["location"]["lat"] - 39.9045) < 0.05
    assert abs(match["location"]["lng"] - 116.4050) < 0.05
    # 不透出厂商原始字段。
    assert "geocodes" not in body and "status" not in body and "count" not in body


def test_resolve_posts_dual_requests_with_stripped_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body([geocode("x", gcj_lat=39.9, gcj_lng=116.4)]),
        ),
    )
    response = resolve(client, "  北京市朝阳区示例路 18 号  ")
    assert response.status_code == 200
    # 串行双查：先 v5 place/text（地标），后 v3 geocode/geo（结构化地址）。
    assert [request.url.path for request in requests] == [
        "/v5/place/text",
        "/v3/geocode/geo",
    ]
    poi_params = dict(requests[0].url.params)
    assert poi_params["key"] == TEST_KEY
    assert poi_params["keywords"] == "北京市朝阳区示例路 18 号"
    # 未提供 city 时不携带城市限定参数。
    assert "city" not in poi_params
    assert "citylimit" not in poi_params
    geo_params = dict(requests[1].url.params)
    assert geo_params["key"] == TEST_KEY
    assert geo_params["address"] == "北京市朝阳区示例路 18 号"
    assert "city" not in geo_params


def test_resolve_returns_all_candidates_in_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
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
        amap_transport(
            requests,
            geocode_payload=ok_body(
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
    patch_client(monkeypatch, amap_transport(requests, geocode_payload=ok_body([])))
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
        amap_transport(
            requests,
            geocode_payload={
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            },
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
        amap_transport(requests, geocode_payload={"info": "error"}, status_code=500),
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
        amap_transport(requests, geocode_payload={}, text="<html>gateway error</html>"),
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
        amap_transport(requests, geocode_payload=httpx.ConnectTimeout("timed out")),
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
        amap_transport(
            requests,
            geocode_payload=ok_body([geocode("x", gcj_lat=39.9, gcj_lng=116.4)]),
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
        amap_transport(
            requests,
            geocode_payload={"status": "0", "info": "error", "infocode": "10001"},
        ),
    )
    with caplog.at_level(logging.DEBUG):
        response = resolve(client, "用户的私密地址文本")
    assert response.status_code == 502
    assert "用户的私密地址文本" not in caplog.text
    assert TEST_KEY not in caplog.text


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
    patch_client(monkeypatch, transport)
    return closed


def test_resolve_missing_geocodes_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """status=1 但缺失 geocodes 字段是上游结构异常：502，而不是 404。"""
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "0",
            },
        ),
    )
    response = resolve(client)
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_ERROR"
    assert error["retryable"] is True


@pytest.mark.parametrize(
    "bad_geocodes",
    ["nodata", {"0": {}}, 3, True],
)
def test_resolve_nonarray_geocodes_returns_502(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    bad_geocodes: object,
) -> None:
    """geocodes 非数组同样按上游结构异常处理：502。"""
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "geocodes": bad_geocodes,
            },
        ),
    )
    response = resolve(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_resolve_filters_nan_inf_and_out_of_range_candidates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [
                    geocode("非有限纬度", gcj_lat=float("nan"), gcj_lng=116.4050),
                    geocode("非有限经度", gcj_lat=39.9045, gcj_lng=float("inf")),
                    geocode("越界纬度", gcj_lat=999.0, gcj_lng=116.4050),
                    geocode("越界经度", gcj_lat=39.9045, gcj_lng=-1000.0),
                    geocode(
                        "北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050
                    ),
                ]
            ),
        ),
    )
    response = resolve(client)
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert [match["formatted_address"] for match in matches] == [
        "北京市朝阳区示例路 18 号"
    ]
    location = matches[0]["location"]
    assert -90.0 <= location["lat"] <= 90.0
    assert -180.0 <= location["lng"] <= 180.0


def test_resolve_all_candidates_invalid_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [
                    geocode("非有限坐标", gcj_lat=float("nan"), gcj_lng=float("inf")),
                    geocode("越界坐标", gcj_lat=999.0, gcj_lng=-1000.0),
                ]
            ),
        ),
    )
    response = resolve(client)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ADDRESS_NOT_FOUND"


def test_amap_client_closes_after_resolve_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    closed = track_client_close(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [geocode("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050)]
            ),
        ),
    )
    response = resolve(client)
    assert response.status_code == 200
    assert closed == [True]


def test_amap_client_closes_after_resolve_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    closed = track_client_close(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload={
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            },
        ),
    )
    response = resolve(client)
    assert response.status_code == 502
    assert closed == [True]


def test_resolve_city_passed_to_both_upstreams(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [
                    geocode(
                        "上海市黄浦区人民大道185号",
                        gcj_lat=31.2420,
                        gcj_lng=121.4729,
                        level="门址",
                        city="上海市",
                        district="黄浦区",
                    )
                ]
            ),
            text_payload=poi_ok_body(
                [
                    poi_item(
                        "B00157917M", "上海人民广场", gcj_lat=31.2288, gcj_lng=121.4752
                    )
                ]
            ),
        ),
    )
    response = client.post(
        "/api/v1/locations/resolve", json={"address": "人民广场", "city": " 上海市 "}
    )
    assert response.status_code == 200
    # city 去首尾空白后透传两路；v5 附带 citylimit=true 限定城市。
    poi_params = dict(requests[0].url.params)
    assert poi_params["city"] == "上海市"
    assert poi_params["citylimit"] == "true"
    geo_params = dict(requests[1].url.params)
    assert geo_params["city"] == "上海市"
    matches = response.json()["matches"]
    # 门址级 geocode 排最前，POI 随后；geocode 候选携带省市区。
    assert [match["match_kind"] for match in matches] == ["geocode", "poi"]
    assert matches[0]["level"] == "门址"
    assert matches[0]["city"] == "上海市"
    assert matches[0]["district"] == "黄浦区"
    assert matches[1]["name"] == "上海人民广场"


@pytest.mark.parametrize("city", ["", "   ", "a" * 21, 123])
def test_resolve_rejects_invalid_city(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, city: object
) -> None:
    def unexpected_client() -> object:
        raise AssertionError("输入校验失败时不应调用高德")

    monkeypatch.setattr(nearby_service, "_amap_client", unexpected_client)
    response = client.post(
        "/api/v1/locations/resolve", json={"address": "人民广场", "city": city}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_resolve_orders_door_geocode_poi_then_other_geocode_and_caps_at_five(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """契约 #62：门址级 geocode 最前、POI 次之、其余 geocode 殿后。

    上限 5 条由合并排序自然截断（不为两路保留名额）：POI 足够多时
    道路级 geocode 候选被挤出，属预期行为。
    """
    requests: list[httpx.Request] = []
    geocodes = [
        geocode(
            "上海市黄浦区人民大道185号",
            gcj_lat=31.2420,
            gcj_lng=121.4729,
            level="门址",
            city="上海市",
            district="黄浦区",
        ),
        geocode(
            "上海市人民大道",
            gcj_lat=31.2421,
            gcj_lng=121.4730,
            level="道路",
            city="上海市",
            district="黄浦区",
        ),
    ]
    pois = [
        poi_item("B00157917M", "上海人民广场", gcj_lat=31.2288, gcj_lng=121.4752),
        poi_item("B0FFG0001", "人民广场地铁站", gcj_lat=31.2330, gcj_lng=121.4740),
        poi_item("B0FFG0002", "人民广场(福州路)", gcj_lat=31.2335, gcj_lng=121.4750),
        poi_item("B0FFG0003", "新世界城", gcj_lat=31.2340, gcj_lng=121.4760),
        poi_item("B0FFG0004", "上海城市规划展示馆", gcj_lat=31.2345, gcj_lng=121.4770),
    ]
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(geocodes),
            text_payload=poi_ok_body(pois),
        ),
    )
    response = resolve(client, "人民广场")
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 5
    assert matches[0]["match_kind"] == "geocode"
    assert matches[0]["level"] == "门址"
    assert [match["match_kind"] for match in matches[1:]] == ["poi"] * 4
    # 道路级 geocode 被 POI 挤出上限，不返回。
    assert all(match["level"] != "道路" for match in matches)


def test_resolve_poi_candidates_expose_name_city_district(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            text_payload=poi_ok_body(
                [
                    poi_item(
                        "B00157917M",
                        "上海人民广场",
                        gcj_lat=31.2288,
                        gcj_lng=121.4752,
                        address="黄浦区",
                    )
                ]
            ),
        ),
    )
    response = resolve(client, "人民广场")
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert set(match.keys()) == {
        "formatted_address",
        "name",
        "city",
        "district",
        "level",
        "match_kind",
        "location",
        "data_source",
    }
    assert match["match_kind"] == "poi"
    assert match["name"] == "上海人民广场"
    assert match["city"] == "上海市"
    assert match["district"] == "黄浦区"
    assert match["level"] is None
    # 直辖市省市区重复段去重；address=黄浦区 与行政区段相同不再叠加。
    assert match["formatted_address"] == "上海市黄浦区"
    assert match["data_source"] == "amap"


def test_resolve_dedupes_poi_and_geocode_candidates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [
                    geocode(
                        "北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050
                    ),
                    geocode(
                        "北京市朝阳区示例路 18 号", gcj_lat=39.9050, gcj_lng=116.4060
                    ),
                ]
            ),
            text_payload=poi_ok_body(
                [
                    poi_item("B0AAA1", "人民广场", gcj_lat=31.2288, gcj_lng=121.4752),
                    poi_item("B0BBB2", "人民广场", gcj_lat=31.2290, gcj_lng=121.4755),
                ]
            ),
        ),
    )
    response = resolve(client, "人民广场")
    assert response.status_code == 200
    matches = response.json()["matches"]
    # geocode 按 formatted_address 去重、POI 按 (name, city, district, address)
    # 去重后各剩一条；门址级 geocode 仍在最前。
    assert [match["match_kind"] for match in matches] == ["geocode", "poi"]
    assert matches[0]["formatted_address"] == "北京市朝阳区示例路 18 号"
    assert matches[1]["name"] == "人民广场"


def test_resolve_poi_failure_returns_502_even_if_geocode_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """任一路失败整体 502，不静默降级为 geocode-only（契约 #62）。"""
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [geocode("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050)]
            ),
            text_payload={
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            },
        ),
    )
    response = resolve(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_resolve_poi_timeout_returns_504_even_if_geocode_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=ok_body(
                [geocode("北京市朝阳区示例路 18 号", gcj_lat=39.9045, gcj_lng=116.4050)]
            ),
            text_payload=httpx.ReadTimeout("读取超时"),
        ),
    )
    response = resolve(client)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_resolve_geocode_failure_returns_502_and_discards_poi_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POI 成功但随后 geocode 失败 → 整体 502，已取得的 POI 候选不返回。

    与「POI 先失败 fail-fast」属同一 try 块的另一个失败分支：
    第二路（geocode）失败同样不降级为 POI-only 结果（A 评审建议补测）。
    """
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload={
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            },
            text_payload=poi_ok_body(
                [
                    poi_item(
                        "B00157917M", "上海人民广场", gcj_lat=31.2288, gcj_lng=121.4752
                    )
                ]
            ),
        ),
    )
    response = resolve(client, "人民广场")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    # 两路都已发起（串行：text 先、geocode 后），失败发生在第二路。
    assert len(requests) == 2


def test_resolve_geocode_timeout_returns_504_and_discards_poi_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POI 成功但 geocode 超时 → 整体 504，不返回已有 POI 候选。

    HTTPX 5 秒为阶段超时而非请求总时限；本测试只断言错误分类，
    不对端到端耗时作任何保证（前端 15 秒仅是停止等待上限）。
    """
    requests: list[httpx.Request] = []
    patch_client(
        monkeypatch,
        amap_transport(
            requests,
            geocode_payload=httpx.ConnectTimeout("连接超时"),
            text_payload=poi_ok_body(
                [
                    poi_item(
                        "B00157917M", "上海人民广场", gcj_lat=31.2288, gcj_lng=121.4752
                    )
                ]
            ),
        ),
    )
    response = resolve(client, "人民广场")
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert len(requests) == 2
