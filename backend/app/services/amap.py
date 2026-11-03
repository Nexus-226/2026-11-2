"""高德 Web 服务适配器（P1-9 POI 2.0；P1-10 地理编码）。

仅本模块直接接触高德的原始请求与响应：请求前把 WGS84 转为 GCJ-02，
返回的 GCJ-02 坐标转回 WGS84，并把 POI 字段收敛为内部 `AMapPlace`，
地理编码候选收敛为 `AMapGeocodeMatch`，不向 Service、前端或 Agent
暴露厂商原始响应结构或未转换的坐标。密钥只参与请求参数，不写入日志
或异常消息。
"""

import logging
import math
from dataclasses import dataclass

import httpx
from typing_extensions import Self

logger = logging.getLogger(__name__)

# 高德 Web 服务 v5 基础地址；测试可注入 base_url 与 MockTransport。
DEFAULT_BASE_URL = "https://restapi.amap.com"

# GCJ-02 纠偏常量与中国陆地范围：业界通用近似算法，公式与测试向量
# 参考 eviltransform（https://github.com/googollee/eviltransform）。
_EARTH_RADIUS_M = 6378137.0
_FIRST_ECCENTRICITY_SQUARED = 0.00669342162296594323
# (min_lng, min_lat, max_lng, max_lat)
_CHINA_BOUNDS = (72.004, 0.8293, 137.8347, 55.8271)


class AMapError(Exception):
    """高德适配器错误基类；消息不携带密钥或厂商原始响应。"""


class AMapUnavailable(AMapError):
    """高德不可用：网络、HTTP 状态、失败状态码或无法解析的响应。"""


class AMapTimeout(AMapError):
    """高德请求超时。"""


@dataclass(frozen=True)
class AMapPlace:
    """内部 POI 数据；lat/lng 已转换为 WGS84。"""

    poi_id: str
    name: str
    address: str
    phone: str | None
    lat: float
    lng: float
    type_name: str


@dataclass(frozen=True)
class AMapGeocodeMatch:
    """地理编码候选；lat/lng 已转换为 WGS84。"""

    formatted_address: str
    lat: float
    lng: float


def _in_china_mainland(lat: float, lng: float) -> bool:
    min_lng, min_lat, max_lng, max_lat = _CHINA_BOUNDS
    return min_lng < lng < max_lng and min_lat < lat < max_lat


def _transform_lat(x: float, y: float) -> float:
    result = (
        -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    )
    result += (
        (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi))
        * 2.0
        / 3.0
    )
    result += (
        (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    )
    result += (
        (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0))
        * 2.0
        / 3.0
    )
    return result


def _transform_lng(x: float, y: float) -> float:
    result = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    result += (
        (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi))
        * 2.0
        / 3.0
    )
    result += (
        (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    )
    result += (
        (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi))
        * 2.0
        / 3.0
    )
    return result


def wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float]:
    """WGS84 → GCJ-02；中国大陆范围外原样返回。"""
    if not _in_china_mainland(lat, lng):
        return lat, lng
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = 1 - _FIRST_ECCENTRICITY_SQUARED * math.sin(radlat) ** 2
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / (
        (_EARTH_RADIUS_M * (1 - _FIRST_ECCENTRICITY_SQUARED))
        / (magic * sqrt_magic)
        * math.pi
    )
    dlng = (dlng * 180.0) / (_EARTH_RADIUS_M / sqrt_magic * math.cos(radlat) * math.pi)
    return round(lat + dlat, 6), round(lng + dlng, 6)


def gcj02_to_wgs84(lat: float, lng: float) -> tuple[float, float]:
    """GCJ-02 → WGS84：迭代逼近反向纠偏；中国大陆范围外原样返回。"""
    if not _in_china_mainland(lat, lng):
        return lat, lng
    wgs_lat, wgs_lng = lat, lng
    for _ in range(3):
        gcj_lat, gcj_lng = wgs84_to_gcj02(wgs_lat, wgs_lng)
        wgs_lat += lat - gcj_lat
        wgs_lng += lng - gcj_lng
    return round(wgs_lat, 6), round(wgs_lng, 6)


class AMapClient:
    """高德 Web 服务 v5 客户端；本实现按单次请求创建实例使用。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        """关闭底层 HTTP 连接池，避免每次请求泄漏连接。"""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def search_around(
        self, *, lat: float, lng: float, keywords: str, radius_m: int
    ) -> list[AMapPlace]:
        """周边搜索：入参 WGS84 坐标，出参坐标已转回 WGS84。"""
        gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
        payload = self._request(
            "/v5/place/around",
            {
                "key": self._api_key,
                "keywords": keywords,
                "location": f"{gcj_lng:.6f},{gcj_lat:.6f}",
                "radius": str(int(radius_m)),
                "page_size": "25",
                "page_num": "1",
                "show_fields": "business",
            },
        )
        return _parse_pois(payload)

    def get_detail(self, poi_id: str) -> AMapPlace | None:
        """ID 查询详情：未找到返回 None；入参不带 `amap:` 前缀。"""
        payload = self._request(
            "/v5/place/detail",
            {"key": self._api_key, "id": poi_id, "show_fields": "business"},
        )
        pois = _parse_pois(payload)
        if not pois:
            return None
        return pois[0]

    def geocode(self, address: str) -> list[AMapGeocodeMatch]:
        """结构化地址解析（v3 geocode/geo）：候选坐标已转回 WGS84。"""
        payload = self._request(
            "/v3/geocode/geo", {"key": self._api_key, "address": address}
        )
        return _parse_geocodes(payload)

    def _request(self, path: str, params: dict[str, str]) -> dict[str, object]:
        try:
            response = self._client.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise AMapTimeout("高德请求超时") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "高德请求 HTTP 失败：%s status=%s", path, exc.response.status_code
            )
            raise AMapUnavailable("高德服务暂时不可用") from exc
        except httpx.RequestError as exc:
            logger.warning("高德请求连接失败：%s %s", path, type(exc).__name__)
            raise AMapUnavailable("无法连接高德服务") from exc
        except ValueError as exc:
            raise AMapUnavailable("高德返回了无法解析的内容") from exc
        if not isinstance(payload, dict):
            raise AMapUnavailable("高德返回结构异常")
        status = str(payload.get("status", ""))
        if status != "1":
            # 只记录状态信息；请求参数含密钥，绝不写入日志。
            logger.warning(
                "高德返回失败状态：%s status=%s info=%s infocode=%s",
                path,
                status,
                payload.get("info"),
                payload.get("infocode"),
            )
            raise AMapUnavailable("高德接口返回失败状态")
        return payload


def _parse_geocodes(payload: dict[str, object]) -> list[AMapGeocodeMatch]:
    """解析地理编码候选；geocodes 缺失或非数组视为上游异常，空数组为无匹配。"""
    geocodes = payload.get("geocodes")
    if not isinstance(geocodes, list):
        # 与 _parse_pois 一致：geocodes 结构异常按"上游不可用"处理（映射 502），
        # 不能伪装成"无匹配"（映射 404）；合法的空数组才表示无匹配。
        raise AMapUnavailable("高德返回的 geocodes 结构异常")
    matches: list[AMapGeocodeMatch] = []
    for item in geocodes:
        match = _parse_geocode(item)
        if match is not None:
            matches.append(match)
    return matches


def _parse_geocode(item: object) -> AMapGeocodeMatch | None:
    """把单个地理编码候选收敛为内部结构；缺失关键字段时跳过该条。"""
    if not isinstance(item, dict):
        return None
    formatted_address = _clean_text(item.get("formatted_address"))
    if formatted_address is None:
        return None
    gcj_lat, gcj_lng = _parse_gcj02_location(item.get("location"))
    if gcj_lat is None or gcj_lng is None:
        return None
    lat, lng = gcj02_to_wgs84(gcj_lat, gcj_lng)
    return AMapGeocodeMatch(formatted_address=formatted_address, lat=lat, lng=lng)


def _parse_pois(payload: dict[str, object]) -> list[AMapPlace]:
    pois = payload.get("pois")
    if not isinstance(pois, list):
        raise AMapUnavailable("高德返回的 pois 结构异常")
    places: list[AMapPlace] = []
    for poi in pois:
        place = _parse_poi(poi)
        if place is not None:
            places.append(place)
    return places


def _parse_poi(poi: object) -> AMapPlace | None:
    """把单个高德 POI 收敛为内部结构；缺失关键字段时跳过该条。"""
    if not isinstance(poi, dict):
        return None
    poi_id = poi.get("id")
    name = poi.get("name")
    if not isinstance(poi_id, str) or not poi_id.strip():
        return None
    if not isinstance(name, str) or not name.strip():
        return None
    gcj_lat, gcj_lng = _parse_gcj02_location(poi.get("location"))
    if gcj_lat is None or gcj_lng is None:
        return None
    lat, lng = gcj02_to_wgs84(gcj_lat, gcj_lng)
    business = poi.get("business")
    tel = business.get("tel") if isinstance(business, dict) else None
    return AMapPlace(
        poi_id=poi_id.strip(),
        name=name.strip(),
        address=_clean_text(poi.get("address")) or "",
        phone=_clean_text(tel),
        lat=lat,
        lng=lng,
        type_name=_clean_text(poi.get("type")) or "",
    )


def _parse_gcj02_location(location: object) -> tuple[float | None, float | None]:
    """高德坐标为 "lng,lat" 字符串，返回 (lat, lng)。"""
    if not isinstance(location, str):
        return None, None
    parts = location.split(",")
    if len(parts) != 2:
        return None, None
    try:
        lat, lng = float(parts[1]), float(parts[0])
    except ValueError:
        return None, None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None, None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None, None
    return lat, lng


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
