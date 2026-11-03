import type { AddressMatch } from "../types/location";

/** 调用 POST /api/v1/locations/resolve，返回全部候选；不自动选择第一条。 */
export async function resolveAddress(address: string): Promise<AddressMatch[]> {
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
      body: JSON.stringify({ address }),
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) throw new Error("地址解析超时，请重试。");
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
  const data: unknown = await response.json();
  if (!data || typeof data !== "object")
    throw new Error("地址解析返回格式错误。");
  const matches = (data as { matches?: unknown }).matches;
  if (!Array.isArray(matches) || !matches.every(isAddressMatch))
    throw new Error("地址解析返回格式错误。");
  return matches;
}

function isAddressMatch(value: unknown): value is AddressMatch {
  if (!value || typeof value !== "object") return false;
  const m = value as Record<string, unknown>;
  const loc = m.location as Record<string, unknown> | undefined;
  return (
    typeof m.formatted_address === "string" &&
    m.data_source === "amap" &&
    !!loc &&
    Number.isFinite(loc.lat) &&
    Number(loc.lat) >= -90 &&
    Number(loc.lat) <= 90 &&
    Number.isFinite(loc.lng) &&
    Number(loc.lng) >= -180 &&
    Number(loc.lng) <= 180
  );
}
