// WGS84 → GCJ-02 坐标纠偏（eviltransform 公式，与后端 app/services/amap.py
// 同源）。按 docs/API.md 的分工，服务端接口只输出 WGS84；本模块仅用于
// 前端调起第三方地图（如高德导航页）前做坐标适配，属于 C 的职责范围。

const EARTH_RADIUS_M = 6378137.0;
const FIRST_ECCENTRICITY_SQUARED = 0.00669342162296594323;
// 中国陆地范围 (minLng, minLat, maxLng, maxLat)，范围外不纠偏。
const CHINA_BOUNDS = {
  minLng: 72.004,
  minLat: 0.8293,
  maxLng: 137.8347,
  maxLat: 55.8271,
};

export interface GeoPoint {
  lat: number;
  lng: number;
}

function inChinaMainland(lat: number, lng: number): boolean {
  return (
    lng > CHINA_BOUNDS.minLng &&
    lng < CHINA_BOUNDS.maxLng &&
    lat > CHINA_BOUNDS.minLat &&
    lat < CHINA_BOUNDS.maxLat
  );
}

function transformLat(x: number, y: number): number {
  let result =
    -100.0 +
    2.0 * x +
    3.0 * y +
    0.2 * y * y +
    0.1 * x * y +
    0.2 * Math.sqrt(Math.abs(x));
  result +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  result +=
    ((20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin((y / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  result +=
    ((160.0 * Math.sin((y / 12.0) * Math.PI) +
      320.0 * Math.sin((y * Math.PI) / 30.0)) *
      2.0) /
    3.0;
  return result;
}

function transformLng(x: number, y: number): number {
  let result =
    300.0 +
    x +
    2.0 * y +
    0.1 * x * x +
    0.1 * x * y +
    0.1 * Math.sqrt(Math.abs(x));
  result +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  result +=
    ((20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin((x / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  result +=
    ((150.0 * Math.sin((x / 12.0) * Math.PI) +
      300.0 * Math.sin((x / 30.0) * Math.PI)) *
      2.0) /
    3.0;
  return result;
}

function round6(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

export function wgs84ToGcj02(lat: number, lng: number): GeoPoint {
  if (!inChinaMainland(lat, lng)) return { lat, lng };
  const dLat = transformLat(lng - 105.0, lat - 35.0);
  const dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = (lat / 180.0) * Math.PI;
  const magic = 1 - FIRST_ECCENTRICITY_SQUARED * Math.sin(radLat) ** 2;
  const sqrtMagic = Math.sqrt(magic);
  const offsetLat =
    (dLat * 180.0) /
    (((EARTH_RADIUS_M * (1 - FIRST_ECCENTRICITY_SQUARED)) /
      (magic * sqrtMagic)) *
      Math.PI);
  const offsetLng =
    (dLng * 180.0) /
    ((EARTH_RADIUS_M / sqrtMagic) * Math.cos(radLat) * Math.PI);
  return { lat: round6(lat + offsetLat), lng: round6(lng + offsetLng) };
}
