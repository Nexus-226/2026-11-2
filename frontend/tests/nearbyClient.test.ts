// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { nearbyClient } from "../src/api/nearby";

afterEach(() => vi.unstubAllGlobals());

it("passes the exact query center and category without switching to demo on failure", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: async () => ({ error: { message: "服务暂不可用" } }),
  });
  vi.stubGlobal("fetch", fetcher);
  await expect(
    nearbyClient.search({
      lat: 31.2,
      lng: 121.4,
      type: "pet_store",
      radius_m: 5000,
      center_source: "resolved_address",
    }),
  ).rejects.toThrow("服务暂不可用");
  expect(fetcher).toHaveBeenCalledTimes(1);
  const url = new URL(fetcher.mock.calls[0][0], "http://localhost");
  expect(Object.fromEntries(url.searchParams)).toEqual({
    lat: "31.2",
    lng: "121.4",
    type: "pet_store",
    radius_m: "5000",
    center_source: "resolved_address",
  });
});

it("only requests the explicit demo endpoint and rejects malformed results", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ places: [], search_center: {} }),
  });
  vi.stubGlobal("fetch", fetcher);
  await expect(
    nearbyClient.searchDemoRegion("pet_grooming", 1000),
  ).rejects.toThrow("附近服务返回格式错误");
  expect(fetcher.mock.calls[0][0]).toBe(
    "/api/v1/nearby/demo?type=pet_grooming&radius_m=1000",
  );
});
