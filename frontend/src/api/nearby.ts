import type {
  AddressMatch,
  NearbyCategory,
  NearbyResponse,
} from "../types/nearby";

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
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    response = await fetch(`/api/v1/nearby${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted)
      throw new Error("附近服务查询超时，请重试。");
    throw new Error("无法连接后端，请检查服务后重试。");
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (typeof body?.error?.message === "string")
        message = body.error.message;
    } catch {
      /* status fallback */
    }
    throw new Error(message);
  }
  const data = await response.json();
  if (
    !data ||
    !Array.isArray(data.places) ||
    !data.search_center ||
    !validLocation(data.search_center.location) ||
    !["user_location", "resolved_address", "demo_region"].includes(
      data.search_center.source,
    ) ||
    typeof data.search_center.label !== "string" ||
    !["demo", "amap"].includes(data.source) ||
    ![null, "amap_unavailable", "amap_not_configured"].includes(
      data.fallback_reason,
    ) ||
    !data.places.every(
      (place: Record<string, unknown>) =>
        place &&
        typeof place.id === "string" &&
        typeof place.name === "string" &&
        typeof place.address === "string" &&
        (place.phone === null || typeof place.phone === "string") &&
        ["pet_hospital", "pet_grooming", "pet_store"].includes(
          String(place.category),
        ) &&
        ["open", "closed", "unknown"].includes(String(place.business_status)) &&
        ["demo", "amap"].includes(String(place.data_source)) &&
        Number.isInteger(place.distance_m) &&
        Number(place.distance_m) >= 0 &&
        validLocation(place.location),
    )
  )
    throw new Error("附近服务返回格式错误。");
  return data as NearbyResponse;
}

function validLocation(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const { lat, lng } = value as { lat: number; lng: number };
  return (
    Number.isFinite(lat) &&
    lat >= -90 &&
    lat <= 90 &&
    Number.isFinite(lng) &&
    lng >= -180 &&
    lng <= 180
  );
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

function validMatch(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const match = value as Record<string, unknown>;
  return (
    typeof match.formatted_address === "string" &&
    match.formatted_address.trim().length > 0 &&
    ["name", "city", "district", "level"].every(
      (key) => match[key] === null || typeof match[key] === "string",
    ) &&
    (match.match_kind === "poi" || match.match_kind === "geocode") &&
    match.data_source === "amap" &&
    validLocation(match.location)
  );
}

export async function resolveAddress(
  address: string,
  city?: string,
): Promise<AddressMatch[]> {
  let response: Response;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    response = await fetch("/api/v1/locations/resolve", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        address: address.trim(),
        ...(city?.trim() ? { city: city.trim() } : {}),
      }),
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted)
      throw new Error("地址解析请求超时，请重试。");
    throw new Error("无法连接后端，请检查服务后重试。");
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    let message = `地址解析失败（${response.status}）`;
    try {
      const body = await response.json();
      if (typeof body?.error?.message === "string")
        message = body.error.message;
    } catch {
      /* status fallback */
    }
    throw new Error(message);
  }
  const data = await response.json();
  if (!data || !Array.isArray(data.matches) || !data.matches.every(validMatch))
    throw new Error("地址解析返回格式错误。");
  return data.matches as AddressMatch[];
}
