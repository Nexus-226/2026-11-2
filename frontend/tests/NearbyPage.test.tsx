// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import NearbyPage from "../src/pages/NearbyPage";
import type { AddressMatch, NearbyResponse, Place } from "../src/types/nearby";

const mocks = vi.hoisted(() => ({
  search: vi.fn(),
  searchDemoRegion: vi.fn(),
  resolveAddress: vi.fn(),
}));
vi.mock("../src/api/nearby", () => ({
  nearbyClient: mocks,
  resolveAddress: mocks.resolveAddress,
}));

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
        business_hours_today: null,
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
        business_hours_today: null,
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

function amapPlace(overrides?: Partial<Place>): Place {
  return {
    id: "amap:B0REAL1",
    name: "安心宠物医院",
    category: "pet_hospital",
    address: "示例路 18 号",
    phone: null,
    location: { lat: 39.913345, lng: 116.384047 },
    distance_m: 900,
    business_status: "open",
    business_hours_today: "09:00-21:00",
    navigation_url: null,
    data_source: "amap",
    ...overrides,
  };
}

function amapResponse(places: Place[]): NearbyResponse {
  return {
    places,
    search_center: {
      location: { lat: 39.91, lng: 116.4 },
      source: "user_location",
      label: "当前位置",
    },
    source: "amap",
    fallback_reason: null,
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

function addressMatch(
  formatted: string,
  lat: number,
  lng: number,
): AddressMatch {
  return {
    formatted_address: formatted,
    name: null,
    city: null,
    district: null,
    level: "门址",
    match_kind: "geocode",
    location: { lat, lng },
    data_source: "amap",
  };
}

function addressResponse(): NearbyResponse {
  return demoResponse({
    search_center: {
      location: { lat: 39.96, lng: 116.31 },
      source: "resolved_address",
      label: "所选地址",
    },
    fallback_reason: "amap_not_configured",
  });
}

it("shows disambiguating POI metadata, requires a click, and uses the selected name as center", async () => {
  mocks.resolveAddress.mockResolvedValue([
    {
      ...addressMatch("上海市黄浦区人民大道185号", 31.23, 121.47),
      name: "上海人民广场",
      city: "上海市",
      district: "黄浦区",
      level: null,
      match_kind: "poi",
    },
    {
      ...addressMatch("上海市人民广场", 31.24, 121.47),
      city: "上海市",
      district: null,
      level: "道路",
    },
  ]);
  mocks.search.mockResolvedValue(
    demoResponse({
      search_center: {
        source: "resolved_address",
        label: "所选地址",
        location: { lat: 31.23, lng: 121.47 },
      },
    }),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  expect(screen.getByText(/未填写城市，将在全国搜索/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("城市（可选）"), {
    target: { value: "上海市" },
  });
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "人民广场" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  await screen.findByText("上海人民广场");
  expect(screen.getByText("上海市 · 黄浦区")).toBeTruthy();
  expect(screen.getByText(/地址解析结果 · 精度：道路/)).toBeTruthy();
  expect(mocks.resolveAddress).toHaveBeenCalledWith("人民广场", "上海市");
  expect(mocks.search).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("上海人民广场"));
  await screen.findByText(/查询中心：上海人民广场 · 上海市黄浦区人民大道185号/);
});

it("clears old candidates on editing and ignores a late resolution after switching to demo", async () => {
  render(<NearbyPage onNavigate={() => {}} />);
  mocks.resolveAddress.mockResolvedValue([addressMatch("旧地址", 39.9, 116.4)]);
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "旧地址" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  await screen.findByText("旧地址");
  fireEvent.change(screen.getByLabelText("城市（可选）"), {
    target: { value: "上海市" },
  });
  expect(screen.queryByText("旧地址")).toBeNull();
  let finish!: (matches: AddressMatch[]) => void;
  mocks.resolveAddress.mockReturnValue(
    new Promise<AddressMatch[]>((resolve) => {
      finish = resolve;
    }),
  );
  fireEvent.click(screen.getByText("解析地址"));
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText(/查询中心：演示区域中心/);
  await act(async () => finish([addressMatch("迟到地址", 31.2, 121.4)]));
  expect(screen.queryByText("迟到地址")).toBeNull();
  expect(mocks.search).not.toHaveBeenCalled();
});

async function selectAddress() {
  mocks.resolveAddress.mockResolvedValue([
    addressMatch("北京市海淀区幸福路 1 号", 39.96, 116.31),
  ]);
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "幸福路 1 号" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  fireEvent.click(await screen.findByText("北京市海淀区幸福路 1 号"));
}

it("keeps the chosen address visible through fallback, filters and retry", async () => {
  mocks.search.mockResolvedValue(addressResponse());
  render(<NearbyPage onNavigate={() => {}} />);
  await selectAddress();
  const center = /查询中心：北京市海淀区幸福路 1 号/;
  await screen.findByText(center);
  fireEvent.click(screen.getByText("宠物美容"));
  await screen.findByText(center);
  expect(mocks.search).toHaveBeenLastCalledWith({
    lat: 39.96,
    lng: 116.31,
    type: "pet_grooming",
    radius_m: 3000,
    center_source: "resolved_address",
  });
  fireEvent.change(screen.getByLabelText("搜索半径"), {
    target: { value: "1000" },
  });
  await screen.findByText(center);
  expect(mocks.search).toHaveBeenLastCalledWith(
    expect.objectContaining({ radius_m: 1000 }),
  );
  mocks.search.mockRejectedValueOnce(new Error("暂时不可用"));
  fireEvent.click(screen.getByText("重新查询"));
  await screen.findByRole("alert");
  expect(screen.queryByText(center)).toBeNull();
  fireEvent.click(screen.getByText("重试"));
  await screen.findByText(center);
});

it("replaces the address center when switching to demo and successful geolocation", async () => {
  mocks.search.mockResolvedValueOnce(addressResponse());
  render(<NearbyPage onNavigate={() => {}} />);
  await selectAddress();
  await screen.findByText(/查询中心：北京市海淀区幸福路 1 号/);
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText(/查询中心：演示区域中心/);
  expect(screen.queryByText(/查询中心：北京市海淀区/)).toBeNull();
  geo.getCurrentPosition.mockImplementation((success) =>
    success({ coords: { latitude: 31.2304, longitude: 121.4737 } }),
  );
  mocks.search.mockResolvedValue(
    demoResponse({
      source: "amap",
      places: [],
      search_center: {
        source: "user_location",
        label: "当前位置",
        location: { lat: 31.2304, lng: 121.4737 },
      },
    }),
  );
  fireEvent.click(screen.getByText("使用我的位置"));
  await screen.findByText(/查询中心：当前位置（纬度 31.2304，经度 121.4737）/);
  expect(screen.queryByText(/查询中心：北京市海淀区/)).toBeNull();
  expect(mocks.search).toHaveBeenLastCalledWith({
    lat: 31.2304,
    lng: 121.4737,
    type: "pet_hospital",
    radius_m: 3000,
    center_source: "user_location",
  });
});

it("does not restore a late address result after switching to demo", async () => {
  let finish!: (response: NearbyResponse) => void;
  mocks.search.mockReturnValue(
    new Promise<NearbyResponse>((resolve) => {
      finish = resolve;
    }),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  await selectAddress();
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText(/查询中心：演示区域中心/);
  await act(async () => finish(addressResponse()));
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByText(/查询中心：演示区域中心/)).toBeTruthy();
  expect(screen.queryByText(/查询中心：北京市海淀区/)).toBeNull();
});

it("resolves typed address and queries nearby after user picks a candidate", async () => {
  mocks.resolveAddress.mockResolvedValue([
    addressMatch("北京市朝阳区幸福路 1 号", 39.91, 116.41),
    addressMatch("北京市海淀区幸福路 1 号", 39.96, 116.31),
  ]);
  mocks.search.mockResolvedValue(demoResponse());
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "  幸福路 1 号  " },
  });
  fireEvent.click(screen.getByText("解析地址"));
  await screen.findByText("北京市朝阳区幸福路 1 号");
  await screen.findByText("北京市海淀区幸福路 1 号");
  // 候选返回后不自动选择第一条，也不自动查询附近。
  expect(mocks.search).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("北京市海淀区幸福路 1 号"));
  await waitFor(() =>
    expect(mocks.search).toHaveBeenCalledWith(
      expect.objectContaining({
        lat: 39.96,
        lng: 116.31,
        center_source: "resolved_address",
      }),
    ),
  );
  expect(mocks.resolveAddress).toHaveBeenCalledWith("幸福路 1 号", undefined);
});

it("shows address resolve errors without querying nearby", async () => {
  mocks.resolveAddress.mockRejectedValue(
    new Error("未找到匹配的地址，请尝试输入更完整的地址"),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "不存在的地方" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("未找到匹配的地址");
  expect(mocks.search).not.toHaveBeenCalled();
});

it("keeps address fallback usable after geolocation denial", async () => {
  geo.getCurrentPosition.mockImplementation(
    (_success: unknown, onError: (e: unknown) => void) => {
      onError(new Error("denied"));
    },
  );
  mocks.resolveAddress.mockResolvedValue([
    addressMatch("北京市朝阳区幸福路 1 号", 39.91, 116.41),
  ]);
  mocks.search.mockResolvedValue(demoResponse());
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  await screen.findByRole("alert");
  // 拒绝定位后地址输入仍可用，选择候选即以 resolved_address 查询。
  fireEvent.change(screen.getByLabelText("地址"), {
    target: { value: "北京市朝阳区幸福路 1 号" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  const candidate = await screen.findByText("北京市朝阳区幸福路 1 号");
  fireEvent.click(candidate);
  await waitFor(() =>
    expect(mocks.search).toHaveBeenCalledWith(
      expect.objectContaining({
        lat: 39.91,
        lng: 116.41,
        center_source: "resolved_address",
      }),
    ),
  );
});

it("offers user-triggered amap navigation only for real places", async () => {
  mocks.searchDemoRegion.mockResolvedValue(
    demoResponse({
      places: [
        {
          id: "demo:pet-hospital-01",
          name: "演示动物医院（示例）",
          category: "pet_hospital",
          address: "示例市演示区和平街 1 号",
          phone: null,
          location: { lat: 39.9041, lng: 116.4021 },
          distance_m: 480,
          business_status: "unknown",
          business_hours_today: null,
          navigation_url: null,
          data_source: "demo",
        },
        {
          id: "amap:B0REAL1",
          name: "安心宠物医院",
          category: "pet_hospital",
          address: "示例路 18 号",
          phone: null,
          location: { lat: 39.913345, lng: 116.384047 },
          distance_m: 900,
          business_status: "unknown",
          business_hours_today: null,
          navigation_url: null,
          data_source: "amap",
        },
      ],
    }),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText("安心宠物医院");
  const nav = screen.getByRole("link", { name: /安心宠物医院的高德导航/ });
  const href = nav.getAttribute("href");
  // 导航链接由前端把 WGS84 转为 GCJ-02 后指向高德路径规划页，仅用户点击时打开；
  // 坐标转换精度由 coords.test.ts 的 eviltransform 向量覆盖。
  expect(href).toContain("https://uri.amap.com/navigation?to=");
  expect(href).not.toContain("116.384047");
  expect(href).not.toContain("39.913345");
  expect(href).toContain(encodeURIComponent("安心宠物医院"));
  expect(nav.getAttribute("rel")).toBe("noopener noreferrer");
  expect(nav.getAttribute("target")).toBe("_blank");
  // 演示地点是虚构数据，不提供导航入口。
  expect(screen.queryByRole("link", { name: /演示动物医院/ })).toBeNull();
});

it("shows today's business hours and marks inferred status for real places", async () => {
  geo.getCurrentPosition.mockImplementation(
    (
      success: (p: { coords: { latitude: number; longitude: number } }) => void,
    ) => success({ coords: { latitude: 39.91, longitude: 116.4 } }),
  );
  mocks.search.mockResolvedValue(
    amapResponse([
      amapPlace({
        business_status: "open",
        business_hours_today: "09:00-21:00",
      }),
    ]),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  await screen.findByText("安心宠物医院");
  expect(screen.getByText("今日营业时间：09:00-21:00")).toBeTruthy();
  // 状态来自营业时间推算，须明确标注，避免用户误以为是高德直接给出的状态。
  expect(screen.getByText(/按营业时间推算/)).toBeTruthy();
});

it("shows raw business hours without an open/closed conclusion when unparseable", async () => {
  geo.getCurrentPosition.mockImplementation(
    (
      success: (p: { coords: { latitude: number; longitude: number } }) => void,
    ) => success({ coords: { latitude: 39.91, longitude: 116.4 } }),
  );
  mocks.search.mockResolvedValue(
    amapResponse([
      amapPlace({
        business_status: "unknown",
        business_hours_today: "周末休息",
      }),
    ]),
  );
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("查找附近的宠物服务"));
  await screen.findByText("安心宠物医院");
  // 原文透出供展示，但状态保持 unknown，不给开关门结论、不标「推算」。
  expect(screen.getByText("今日营业时间：周末休息")).toBeTruthy();
  expect(screen.getByText(/营业状态未知/)).toBeTruthy();
  expect(screen.queryByText(/按营业时间推算/)).toBeNull();
});

it("does not mark demo places as inferred and shows no business hours", async () => {
  render(<NearbyPage onNavigate={() => {}} />);
  fireEvent.click(screen.getByText("使用演示区域"));
  await screen.findByText("演示动物医院（示例）");
  // 演示地点的 business_status 是固定值、business_hours_today 恒为 null，
  // 因此不显示营业时间，也不标注「按营业时间推算」。
  expect(screen.queryByText(/今日营业时间/)).toBeNull();
  expect(screen.queryByText(/按营业时间推算/)).toBeNull();
});
