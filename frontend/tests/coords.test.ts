import { describe, expect, it } from "vitest";
import { wgs84ToGcj02 } from "../src/lib/coords";

// 测试向量与后端 app/services/amap.py（P1-9）一致，来自 eviltransform
// 公开测试数据，保证前后端对同一坐标得到一致的高德坐标。
const vectors: Array<[number, number, number, number]> = [
  [39.911954, 116.377817, 39.913345, 116.384047], // 北京
  [31.1774276, 121.5272106, 31.175304, 121.531542], // 上海
  [22.543847, 113.912316, 22.540796, 113.917176], // 深圳
];

describe("wgs84ToGcj02", () => {
  it.each(vectors)(
    "converts WGS84 (%f, %f) to GCJ-02 within tolerance",
    (wgsLat, wgsLng, gcjLat, gcjLng) => {
      const gcj = wgs84ToGcj02(wgsLat, wgsLng);
      expect(gcj.lat).toBeCloseTo(gcjLat, 4);
      expect(gcj.lng).toBeCloseTo(gcjLng, 4);
    },
  );

  it("keeps coordinates outside Chinese mainland unchanged", () => {
    expect(wgs84ToGcj02(35.0, 139.0)).toEqual({ lat: 35.0, lng: 139.0 });
    expect(wgs84ToGcj02(0.5, 100.0)).toEqual({ lat: 0.5, lng: 100.0 });
  });
});
