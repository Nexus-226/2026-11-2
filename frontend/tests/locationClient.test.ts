// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { resolveAddress } from "../src/api/locations";

afterEach(() => {
  vi.unstubAllGlobals();
});

const jsonResponse = (body: unknown, status = 200) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response;

it("returns matches on success", async () => {
  const match = {
    formatted_address: "北京市示例路 18 号",
    location: { lat: 39.9001, lng: 116.4001 },
    data_source: "amap",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse({ matches: [match] })),
  );
  const result = await resolveAddress("北京市示例路 18 号");
  expect(result).toEqual([match]);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/locations/resolve",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ address: "北京市示例路 18 号" }),
    }),
  );
});

it("throws the server error message", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        jsonResponse(
          { error: { code: "ADDRESS_NOT_FOUND", message: "未找到匹配地址" } },
          404,
        ),
      ),
  );
  await expect(resolveAddress("不存在的地方")).rejects.toThrow(
    "未找到匹配地址",
  );
});

it("rejects malformed responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse({ matches: [{ foo: "bar" }] })),
  );
  await expect(resolveAddress("x")).rejects.toThrow("地址解析返回格式错误。");
});
