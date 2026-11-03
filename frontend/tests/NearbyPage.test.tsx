// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import NearbyPage from "../src/pages/NearbyPage";
import type { NearbyResponse } from "../src/types/nearby";

const mocks = vi.hoisted(() => ({
  search: vi.fn(),
  searchDemoRegion: vi.fn(),
}));
vi.mock("../src/api/nearby", () => ({ nearbyClient: mocks }));

const geo = {
  getCurrentPosition: vi.fn(),
};

function demoResponse(overrides?: Partial<NearbyResponse>): NearbyResponse {
  return {
    places: [
      {
        id: "demo:pet-hospital-01",
        name: "演示动物医院（示例）",
        category: "pet_hospital",
        address: "示例市演示区和平街 1 号",
        phone: "010-00000000",
        location: { lat: 39.9041, lng: 116.4021 },
        distance_m: 480,
        business_status: "unknown",
        navigation_url: null,
        data_source: "demo",
      },
      {
        id: "demo:pet-hospital-02",
        name: "演示宠物诊所（示例）",
        category: "pet_hospital",
        address: "示例市演示区中山路 2 号",
        phone: null,
        location: { lat: 39.9201, lng: 116.3901 },
        distance_m: 2381,
        business_status: "open",
        navigation_url: null,
        data_source: "demo",
      },
    ],
    search_center: {
      location: { lat: 39.9001, lng: 116.4001 },
      source: "demo_region",
      label: "演示区域中心",
    },
    source: "demo",
    fallback_reason: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.searchDemoRegion.mockResolvedValue(demoResponse());
  Object.defineProperty(navigator, "geolocation", {
    value: geo,
    configurable: true,
  });
});
afterEach(cleanup);

it("labels fallback empty results without claiming real nearby services are absent", async () => {
  mocks.searchDemoRegion.mockResolvedValue(
    demoResponse({
      places: [],
      fallback_reason: "amap_unavailable",
    }),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText(/实时服务暂时不可用/);
  expect(screen.getByText(/这不代表真实附近没有宠物服务/)).toBeTruthy();
});

it("shows errors and retries without making up results", async () => {
  mocks.searchDemoRegion.mockRejectedValueOnce(new Error("后端不可用"));
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("使用演示区域"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "后端不可用",
  );
  expect(screen.queryByText("演示动物医院（示例）")).toBeNull();
  fireEvent.click(screen.getByText("重试"));
  await screen.findByText("演示动物医院（示例）");
});

it("ignores late location callbacks after switching to demo", async () => {
  let located!: (p: {
    coords: { latitude: number; longitude: number };
  }) => void;
  geo.getCurrentPosition.mockImplementation((success) => {
    located = success;
  });
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  fireEvent.click(screen.getByRole("button", { name: "使用演示区域" }));
  await screen.findByText("演示动物医院（示例）");
  located({ coords: { latitude: 1, longitude: 2 } });
  await waitFor(() => expect(mocks.search).not.toHaveBeenCalled());
  expect(screen.getByText(/查询中心：演示区域中心/)).toBeTruthy();
});

it("uses cached location when changing radius", async () => {
  geo.getCurrentPosition.mockImplementation((success) =>
    success({
      coords: { latitude: 39.91, longitude: 116.4 },
    }),
  );
  mocks.search.mockResolvedValue(demoResponse());
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  await screen.findByText("演示动物医院（示例）");
  fireEvent.change(screen.getByLabelText("搜索半径"), {
    target: { value: "5000" },
  });
  await waitFor(() =>
    expect(mocks.search).toHaveBeenLastCalledWith(
      expect.objectContaining({ radius_m: 5000, lat: 39.91, lng: 116.4 }),
    ),
  );
  expect(geo.getCurrentPosition).toHaveBeenCalledTimes(1);
});

it("shows source labeling for demo region results", async () => {
  render(<NearbyPage onNavigate={() => {}} />);
  expect(screen.getByText(/不会保存你的位置/)).toBeTruthy();
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText("演示动物医院（示例）");
  expect(
    screen.getByText(
      "演示数据 · 以下为内置示例地点，不代表真实商家（非实时）。",
    ),
  ).toBeTruthy();
  expect(screen.getByText(/查询中心：演示区域中心/)).toBeTruthy();
  expect(mocks.searchDemoRegion).toHaveBeenCalledWith("pet_hospital", 3000);
});

it("syncs selection between list and schematic map", async () => {
  render(<NearbyPage onNavigate={() => {}} />);
  await screen.findByText("使用演示区域");
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText("演示动物医院（示例）");
  fireEvent.click(screen.getByText("演示动物医院（示例）"));
  const marker = screen.getByRole("button", { name: /，距离 480 m$/ });
  expect(marker.getAttribute("aria-pressed")).toBe("true");
  const card = screen.getByRole("button", { name: /示例市演示区和平街 1 号/ });
  expect(card.getAttribute("aria-pressed")).toBe("true");
});

it("suggests demo region when geolocation is denied", async () => {
  geo.getCurrentPosition.mockImplementation(
    (_success: unknown, onError: (e: unknown) => void) => {
      onError(new Error("denied"));
    },
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("使用演示区域");
  expect(mocks.search).not.toHaveBeenCalled();
  expect(mocks.searchDemoRegion).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "使用演示区域" }));
  await screen.findByText("演示动物医院（示例）");
  expect(mocks.searchDemoRegion).toHaveBeenCalledTimes(1);
});

it("queries with user location and labels amap fallback", async () => {
  geo.getCurrentPosition.mockImplementation(
    (
      success: (p: { coords: { latitude: number; longitude: number } }) => void,
    ) => {
      success({ coords: { latitude: 39.91, longitude: 116.4 } });
    },
  );
  mocks.search.mockResolvedValue(
    demoResponse({
      search_center: {
        location: { lat: 39.91, lng: 116.4 },
        source: "user_location",
        label: "当前位置",
      },
      fallback_reason: "amap_not_configured",
    }),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  await screen.findByText(
    "演示数据 · 实时附近服务尚未接入高德，以下为内置示例地点（非实时）。",
  );
  expect(mocks.search).toHaveBeenCalledWith(
    expect.objectContaining({
      lat: 39.91,
      lng: 116.4,
      type: "pet_hospital",
      radius_m: 3000,
      center_source: "user_location",
    }),
  );
});

it("re-queries demo region when switching category", async () => {
  render(<NearbyPage onNavigate={() => {}} />);
  await screen.findByText("使用演示区域");
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText("演示动物医院（示例）");
  fireEvent.click(screen.getByText("宠物美容"));
  await waitFor(() =>
    expect(mocks.searchDemoRegion).toHaveBeenLastCalledWith(
      "pet_grooming",
      3000,
    ),
  );
});
