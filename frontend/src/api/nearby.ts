import type { NearbyCategory, NearbyResponse } from "../types/nearby";

export type NearbyCenterSource = "user_location" | "resolved_address";

export interface NearbyQuery {
  lat: number;
  lng: number;
  type: NearbyCategory;
  radius_m: number;
  center_source: NearbyCenterSource;
}

async function request(path: string): Promise<NearbyResponse> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/nearby${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new Error("无法连接后端，请检查服务后重试。");
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (typeof body?.error?.message === "string") message = body.error.message;
    } catch {
      /* status fallback */
    }
    throw new Error(message);
  }
  const data = await response.json();
  if (!data || !Array.isArray(data.places) || !data.search_center)
    throw new Error("附近服务返回格式错误。");
  return data as NearbyResponse;
}

export const nearbyClient = {
  search(query: NearbyQuery): Promise<NearbyResponse> {
    const params = new URLSearchParams({
      lat: String(query.lat),
      lng: String(query.lng),
      type: query.type,
      radius_m: String(query.radius_m),
      center_source: query.center_source,
    });
    return request(`?${params}`);
  },
  searchDemoRegion(
    type: NearbyCategory,
    radiusM: number,
  ): Promise<NearbyResponse> {
    const params = new URLSearchParams({ type, radius_m: String(radiusM) });
    return request(`/demo?${params}`);
  },
};
