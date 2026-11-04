// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { nearbyClient, resolveAddress } from "../src/api/nearby";

afterEach(() => vi.unstubAllGlobals());

const match = {
  formatted_address: "上海市黄浦区人民大道185号",
  name: "上海人民广场",
  city: "上海市",
  district: "黄浦区",
  level: null,
  match_kind: "poi",
  location: { lat: 31.230761, lng: 121.47068 },
  data_source: "amap",
};

it("passes trimmed explicit city and accepts all candidate fields", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ matches: [match] }) });
  vi.stubGlobal("fetch", fetcher);
  expect(await resolveAddress(" 人民广场 ", " 上海市 ")).toEqual([match]);
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    address: "人民广场",
    city: "上海市",
  });
  await resolveAddress("人民广场", "  ");
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
    address: "人民广场",
  });
});

it.each([
  { ...match, match_kind: "unknown" },
  { ...match, level: [] },
  { ...match, city: undefined },
  { ...match, name: 42 },
])("rejects malformed candidate metadata %#", async (candidate) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ matches: [candidate] }),
    }),
  );
  await expect(resolveAddress("人民广场")).rejects.toThrow(
    "地址解析返回格式错误",
  );
});

it.each([404, 502, 504, 503])(
  "preserves HTTP %s error instead of returning candidates",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status,
        json: async () => ({
          error: {
            message: status === 404 ? "未找到匹配地址" : "地点解析暂不可用",
          },
        }),
      }),
    );
    await expect(resolveAddress("人民广场")).rejects.toThrow(
      status === 404 ? "未找到匹配地址" : "地点解析暂不可用",
    );
  },
);

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
