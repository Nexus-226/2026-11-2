import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import { nearbyClient } from "../api/nearby";
import AddressResolver from "../components/nearby/AddressResolver";
import type { AddressMatch } from "../types/location";
import {
  type NearbyCategory,
  type NearbyResponse,
  type Place,
} from "../types/nearby";
import "../styles/nearby.css";

const radiusOptions = [
  { value: 1000, label: "1 km" },
  { value: 3000, label: "3 km" },
  { value: 5000, label: "5 km" },
  { value: 10000, label: "10 km" },
  { value: 20000, label: "20 km" },
];

const categoryLabels: Record<NearbyCategory, string> = {
  pet_hospital: "宠物医院",
  pet_grooming: "宠物美容",
  pet_store: "宠物用品店",
};

const businessLabels: Record<Place["business_status"], string> = {
  open: "营业中",
  closed: "已打烊",
  unknown: "营业状态未知",
};

const msg = (e: unknown) =>
  e instanceof Error ? e.message : "操作失败，请重试。";

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`;
}

function getCurrentPosition(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("当前浏览器不支持定位，可使用演示区域查看示例数据。"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        }),
      () =>
        reject(
          new Error("未获得定位授权，可主动选择“使用演示区域”查看示例数据。"),
        ),
      { timeout: 10000, maximumAge: 300000 },
    );
  });
}

function sourceBanner(result: NearbyResponse): string {
  if (result.source === "demo") {
    if (result.fallback_reason === "amap_not_configured")
      return "演示数据 · 实时附近服务尚未接入高德，以下为内置示例地点（非实时）。";
    if (result.fallback_reason === "amap_unavailable")
      return "演示数据 · 实时服务暂时不可用，以下为内置示例地点（非实时）。";
    return "演示数据 · 以下为内置示例地点，不代表真实商家（非实时）。";
  }
  return "数据来源：高德（实时）。";
}

type LoadMode = "locate" | "demo" | "address";

interface MapPoint {
  place: Place;
  x: number;
  y: number;
}

function schematicPoints(result: NearbyResponse): MapPoint[] {
  const center = result.search_center.location;
  const cosLat = Math.cos((center.lat * Math.PI) / 180);
  return result.places.map((place) => ({
    place,
    x: (place.location.lng - center.lng) * 111320 * cosLat,
    y: (center.lat - place.location.lat) * 111320,
  }));
}

export default function NearbyPage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const [category, setCategory] = useState<NearbyCategory>("pet_hospital");
  const [radius, setRadius] = useState(3000);
  const [result, setResult] = useState<NearbyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [started, setStarted] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const modeRef = useRef<LoadMode | null>(null);
  const requestIdRef = useRef(0);
  const centerRef = useRef<{ lat: number; lng: number } | null>(null);
  const resolvedRef = useRef<{
    lat: number;
    lng: number;
    label: string;
  } | null>(null);
  useEffect(
    () => () => {
      requestIdRef.current += 1;
    },
    [],
  );

  async function load(mode: LoadMode, type: NearbyCategory, radiusM: number) {
    const requestId = ++requestIdRef.current;
    modeRef.current = mode;
    setStarted(true);
    setLoading(true);
    setError("");
    setResult(null);
    setSelectedId(null);
    try {
      let data: NearbyResponse;
      if (mode === "locate") {
        const center = centerRef.current ?? (await getCurrentPosition());
        if (requestIdRef.current !== requestId) return;
        centerRef.current = center;
        data = await nearbyClient.search({
          lat: center.lat,
          lng: center.lng,
          type,
          radius_m: radiusM,
          center_source: "user_location",
        });
      } else if (mode === "address") {
        const resolved = resolvedRef.current;
        if (!resolved) throw new Error("请先选择地址候选。");
        data = await nearbyClient.search({
          lat: resolved.lat,
          lng: resolved.lng,
          type,
          radius_m: radiusM,
          center_source: "resolved_address",
        });
      } else {
        data = await nearbyClient.searchDemoRegion(type, radiusM);
      }
      if (requestIdRef.current !== requestId) return;
      setResult(data);
    } catch (e) {
      if (requestIdRef.current !== requestId) return;
      setError(msg(e));
    } finally {
      if (requestIdRef.current === requestId) setLoading(false);
    }
  }

  function changeCategory(next: NearbyCategory) {
    setCategory(next);
    if (modeRef.current) void load(modeRef.current, next, radius);
  }

  function changeRadius(next: number) {
    setRadius(next);
    if (modeRef.current) void load(modeRef.current, category, next);
  }

  function retry() {
    void load(modeRef.current ?? "demo", category, radius);
  }

  function handleResolved(match: AddressMatch) {
    resolvedRef.current = {
      lat: match.location.lat,
      lng: match.location.lng,
      label: match.formatted_address,
    };
    void load("address", category, radius);
  }

  const points = result ? schematicPoints(result) : [];
  const maxAbs = Math.max(
    1,
    ...points.flatMap((point) => [Math.abs(point.x), Math.abs(point.y)]),
  );
  const scale = 108 / maxAbs;

  return (
    <>
      <AppHeader active="nearby" onNavigate={onNavigate} />
      <main className="nearby-page">
        <header>
          <p>NEARBY SERVICES</p>
          <h1>附近服务</h1>
          <p>按距离查看附近的宠物医院、美容和用品店。</p>
        </header>
        {!started && (
          <section className="nearby-guide" aria-label="开始使用">
            <h2>从哪里开始？</h2>
            <p>
              定位仅用于计算你与各地点的距离，不会保存你的位置；也可以主动选择演示区域，浏览内置的示例地点。
            </p>
            <div>
              <button
                type="button"
                disabled={loading}
                onClick={() => void load("locate", category, radius)}
              >
                查找附近的宠物服务
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void load("demo", category, radius)}
              >
                使用演示区域
              </button>
            </div>
            <AddressResolver onResolved={handleResolved} disabled={loading} />
          </section>
        )}
        {started && (
          <div className="nearby-actions">
            <button
              type="button"
              onClick={() => {
                centerRef.current = null;
                void load("locate", category, radius);
              }}
            >
              使用我的位置
            </button>
            <button
              type="button"
              onClick={() => void load("demo", category, radius)}
            >
              使用演示区域
            </button>
            <span>定位仅用于本次查询，不保存；演示区域为非实时位置。</span>
            <AddressResolver onResolved={handleResolved} disabled={loading} />
          </div>
        )}
        {error && (
          <p role="alert">
            {error}
            <button type="button" onClick={retry}>
              重试
            </button>
          </p>
        )}
        {started && (
          <>
            <div className="nearby-toolbar">
              <fieldset className="nearby-categories">
                <legend>地点类别</legend>
                {(Object.keys(categoryLabels) as NearbyCategory[]).map(
                  (item) => (
                    <button
                      key={item}
                      type="button"
                      aria-pressed={category === item}
                      className={
                        category === item
                          ? "category-tab active"
                          : "category-tab"
                      }
                      disabled={loading}
                      onClick={() => changeCategory(item)}
                    >
                      {categoryLabels[item]}
                    </button>
                  ),
                )}
              </fieldset>
              <label className="nearby-radius">
                搜索半径
                <select
                  value={radius}
                  disabled={loading}
                  onChange={(e) => changeRadius(Number(e.target.value))}
                >
                  {radiusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" disabled={loading} onClick={retry}>
                重新查询
              </button>
            </div>
            {loading && <p role="status">正在加载地点…</p>}
            {result && !loading && (
              <>
                <p className="nearby-source">{sourceBanner(result)}</p>
                <p className="nearby-center">
                  查询中心：
                  {modeRef.current === "address" && resolvedRef.current
                    ? resolvedRef.current.label
                    : result.search_center.label}
                  （纬度 {result.search_center.location.lat.toFixed(4)}，经度{" "}
                  {result.search_center.location.lng.toFixed(4)}）
                </p>
                {result.places.length === 0 ? (
                  <p className="nearby-empty">
                    {result.source === "demo"
                      ? "演示数据中没有该距离内的地点，可放大半径或换一类地点；这不代表真实附近没有宠物服务。"
                      : "当前查询范围内没有匹配地点，可放大半径或换一类地点。"}
                  </p>
                ) : (
                  <div className="nearby-layout">
                    <PlaceList
                      places={result.places}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                    />
                    <MapBoundary
                      key={result.search_center.source + category + radius}
                    >
                      <SchematicMap
                        points={points}
                        centerLabel={result.search_center.label}
                        scale={scale}
                        selectedId={selectedId}
                        onSelect={setSelectedId}
                      />
                    </MapBoundary>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>
    </>
  );
}

function PlaceList({
  places,
  selectedId,
  onSelect,
}: {
  places: Place[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <section className="nearby-panel" aria-label="地点列表">
      <h2>地点列表</h2>
      <ul className="place-list">
        {places.map((place) => (
          <li key={place.id}>
            <button
              type="button"
              className={
                selectedId === place.id ? "place-card selected" : "place-card"
              }
              aria-pressed={selectedId === place.id}
              onClick={() =>
                onSelect(selectedId === place.id ? null : place.id)
              }
            >
              <span className="place-top">
                <strong>{place.name}</strong>
                <span className="place-distance">
                  {formatDistance(place.distance_m)}
                </span>
              </span>
              <span className="place-meta">
                {categoryLabels[place.category]} ·{" "}
                {businessLabels[place.business_status]} ·{" "}
                {place.data_source === "demo" ? "演示数据" : "实时数据"}
              </span>
              <span>{place.address}</span>
              <span>{place.phone ?? "暂无电话"}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SchematicMap({
  points,
  centerLabel,
  scale,
  selectedId,
  onSelect,
}: {
  points: MapPoint[];
  centerLabel: string;
  scale: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <section className="nearby-panel" aria-label="位置示意图">
      <h2>位置示意图</h2>
      <p className="map-note">
        按查询中心的相对位置绘制，非真实地图；标记与列表来自同一份结果。
      </p>
      <svg
        className="nearby-map-svg"
        viewBox="-140 -140 280 280"
        role="img"
        aria-label={`位置示意图，共 ${points.length} 个地点`}
      >
        <circle cx={0} cy={0} r={5} className="map-center-dot" />
        <text x={0} y={20} textAnchor="middle" className="map-center-label">
          {centerLabel}
        </text>
        {points.map((point) => {
          const cx = point.x * scale;
          const cy = point.y * scale;
          const selected = selectedId === point.place.id;
          return (
            <g
              key={point.place.id}
              role="button"
              tabIndex={0}
              className={selected ? "map-marker selected" : "map-marker"}
              aria-pressed={selected}
              aria-label={`${point.place.name}，距离 ${formatDistance(point.place.distance_m)}`}
              onClick={() => onSelect(selected ? null : point.place.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(selected ? null : point.place.id);
                }
              }}
            >
              <circle cx={cx} cy={cy} r={selected ? 9 : 6} />
              <text x={cx} y={cy - 13} textAnchor="middle">
                {point.place.name.length > 8
                  ? `${point.place.name.slice(0, 8)}…`
                  : point.place.name}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}

class MapBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p role="status">位置示意图暂时无法显示，请使用地点列表。</p>
    ) : (
      this.props.children
    );
  }
}
