from math import cos, pi, sin, sqrt

from app.schemas import NearbyQuery, NearbyResponse, Place, PlaceCategory


def _outside_mainland_china(lat: float, lng: float) -> bool:
    return not (0.8293 <= lat <= 55.8271 and 72.004 <= lng <= 137.8347)


def wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float, bool]:
    """Convert only within the provider's mainland-China boundary."""
    if _outside_mainland_china(lat, lng):
        return lat, lng, False

    def transform_lat(x: float, y: float) -> float:
        value = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * sqrt(abs(x))
        value += (20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2 / 3
        value += (20 * sin(y * pi) + 40 * sin(y / 3 * pi)) * 2 / 3
        return value + (160 * sin(y / 12 * pi) + 320 * sin(y * pi / 30)) * 2 / 3

    def transform_lng(x: float, y: float) -> float:
        value = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * sqrt(abs(x))
        value += (20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2 / 3
        value += (20 * sin(x * pi) + 40 * sin(x / 3 * pi)) * 2 / 3
        return value + (150 * sin(x / 12 * pi) + 300 * sin(x / 30 * pi)) * 2 / 3

    a, ee = 6378245.0, 0.006693421622965943
    d_lat = transform_lat(lng - 105, lat - 35)
    d_lng = transform_lng(lng - 105, lat - 35)
    rad_lat = lat / 180 * pi
    magic = 1 - ee * sin(rad_lat) ** 2
    sqrt_magic = sqrt(magic)
    d_lat = (d_lat * 180) / ((a * (1 - ee)) / (magic * sqrt_magic) * pi)
    d_lng = (d_lng * 180) / (a / sqrt_magic * cos(rad_lat) * pi)
    return lat + d_lat, lng + d_lng, True


class NearbyService:
    """P1 contract with deterministic mock geocoding and place data."""

    def search(self, query: NearbyQuery) -> NearbyResponse:
        if query.address:
            # Production: inject a geocoder that returns both coordinate and CRS.
            lat, lng, source = 31.2304, 121.4737, "manual_address_mock"
        else:
            lat, lng, source = query.lat, query.lng, "browser"
        assert lat is not None and lng is not None
        provider_lat, provider_lng, converted = wgs84_to_gcj02(lat, lng)
        categories = [query.category] if query.category else list(PlaceCategory)
        labels = {PlaceCategory.HOSPITAL: "安心宠物医院", PlaceCategory.GROOMING: "毛球宠物洗护", PlaceCategory.STORE: "伙伴宠物用品店"}
        places = [Place(id=f"mock-{category.value}", name=labels[category], category=category, address="演示路 18 号（模拟数据）", phone=None, lat=provider_lat + index * 0.001, lng=provider_lng + index * 0.001, distance_m=420 + index * 260, business_status="unknown", data_source="mock") for index, category in enumerate(categories)]
        return NearbyResponse(places=places, provider_crs="GCJ-02" if converted else "WGS-84", coordinate_converted=converted, location_source=source)
