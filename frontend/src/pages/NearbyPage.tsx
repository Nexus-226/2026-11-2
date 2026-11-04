import { useEffect, useRef, useState } from "react";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import { nearbyClient, resolveAddress } from "../api/nearby";
import {
  type AddressMatch,
  type NearbyCategory,
  type NearbyResponse,
  type Place,
} from "../types/nearby";
import { wgs84ToGcj02 } from "../lib/coords";
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

// 后端未提供导航链接时，由前端适配坐标（WGS84 → GCJ-02）后打开高德
// 路径规划页；坐标适配属于前端调起第三方地图的职责（见 docs/API.md）。
// 导航链接仅在用户主动点击时打开，不自动跳转；演示地点为虚构数据，
// 不提供导航入口，避免把虚构位置导航到真实世界。
function navigationHref(place: Place): string {
  if (place.navigation_url) return place.navigation_url;
  const gcj = wgs84ToGcj02(place.location.lat, place.location.lng);
  const name = encodeURIComponent(place.name);
  return `https://uri.amap.com/navigation?to=${gcj.lng},${gcj.lat},${name}&mode=car&src=pet-agent&callnative=0`;
}

type LoadMode = "locate" | "demo" | "address";

export default function NearbyPage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const [category, setCategory] = useState<NearbyCategory>("pet_hospital");
  const [radius, setRadius] = useState(3000);
  const [result, setResult] = useState<NearbyResponse | null>(null);
  const [resolvedAddressLabel, setResolvedAddressLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [started, setStarted] = useState(false);
  const modeRef = useRef<LoadMode | null>(null);
  const requestIdRef = useRef(0);
  const centerRef = useRef<{ lat: number; lng: number } | null>(null);
  const resolvedCenterRef = useRef<AddressMatch | null>(null);
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
    setResolvedAddressLabel("");
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

  async function loadAddress(
    match: AddressMatch,
    type: NearbyCategory,
    radiusM: number,
  ) {
    const requestId = ++requestIdRef.current;
    modeRef.current = "address";
    setStarted(true);
    setLoading(true);
    setError("");
    setResult(null);
    setResolvedAddressLabel("");
    try {
      const data = await nearbyClient.search({
        lat: match.location.lat,
        lng: match.location.lng,
        type,
        radius_m: radiusM,
        center_source: "resolved_address",
      });
      if (requestIdRef.current !== requestId) return;
      setResult(data);
      setResolvedAddressLabel(
        match.name
          ? `${match.name} · ${match.formatted_address}`
          : match.formatted_address,
      );
    } catch (e) {
      if (requestIdRef.current !== requestId) return;
      setError(msg(e));
    } finally {
      if (requestIdRef.current === requestId) setLoading(false);
    }
  }

  function reload(type: NearbyCategory, radiusM: number) {
    const mode = modeRef.current;
    if (mode === "address") {
      const center = resolvedCenterRef.current;
      if (center) void loadAddress(center, type, radiusM);
      return;
    }
    void load(mode ?? "demo", type, radiusM);
  }

  function changeCategory(next: NearbyCategory) {
    setCategory(next);
    if (modeRef.current) reload(next, radius);
  }

  function changeRadius(next: number) {
    setRadius(next);
    if (modeRef.current) reload(category, next);
  }

  function retry() {
    reload(category, radius);
  }

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
        <AddressSearch
          disabled={loading}
          onSelect={(match) => {
            resolvedCenterRef.current = match;
            void loadAddress(match, category, radius);
          }}
        />
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
                  {result.search_center.source === "resolved_address" &&
                  resolvedAddressLabel
                    ? resolvedAddressLabel
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
                  <PlaceList places={result.places} />
                )}
              </>
            )}
          </>
        )}
      </main>
    </>
  );
}

function AddressSearch({
  disabled,
  onSelect,
}: {
  disabled: boolean;
  onSelect: (match: AddressMatch) => void;
}) {
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [matches, setMatches] = useState<AddressMatch[] | null>(null);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState("");
  const resolveIdRef = useRef(0);
  useEffect(() => {
    if (disabled) {
      resolveIdRef.current += 1;
      setResolving(false);
      setMatches(null);
      setError("");
    }
  }, [disabled]);
  useEffect(
    () => () => {
      resolveIdRef.current += 1;
    },
    [],
  );

  async function submit() {
    const text = address.trim();
    if (!text || resolving) return;
    const requestId = ++resolveIdRef.current;
    setResolving(true);
    setError("");
    setMatches(null);
    try {
      const result = await resolveAddress(text, city.trim() || undefined);
      if (resolveIdRef.current !== requestId) return;
      setMatches(result);
    } catch (e) {
      if (resolveIdRef.current !== requestId) return;
      setError(msg(e));
    } finally {
      if (resolveIdRef.current === requestId) setResolving(false);
    }
  }

  return (
    <section className="address-search" aria-label="按地址查找">
      <h2>或者输入地点或地址查找</h2>
      <p>
        拒绝定位或不方便使用定位时，可输入地址并从解析候选中选择，再查询附近服务；多条候选由你自行选择，不会自动使用第一条。地址仅用于本次查询，不会保存。
      </p>
      <div className="address-form">
        <label className="address-label" htmlFor="city-input">
          城市（可选）
        </label>
        <input
          id="city-input"
          className="address-input"
          value={city}
          disabled={disabled || resolving}
          maxLength={20}
          placeholder="例：上海市"
          onChange={(e) => {
            setCity(e.target.value);
            setMatches(null);
            setError("");
          }}
        />
        <label className="address-label" htmlFor="address-input">
          地址
        </label>
        <input
          id="address-input"
          className="address-input"
          value={address}
          disabled={disabled || resolving}
          onChange={(e) => {
            setAddress(e.target.value);
            setMatches(null);
            setError("");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder="例：人民广场，或完整门牌地址"
          maxLength={200}
        />
        <button
          type="button"
          disabled={disabled || resolving || !address.trim()}
          onClick={() => void submit()}
        >
          {resolving ? "解析中…" : "解析地址"}
        </button>
      </div>
      <p>
        {city.trim()
          ? `搜索城市：${city.trim()}`
          : "未填写城市，将在全国搜索；同名地点请核对城市和地址。"}
      </p>
      <p>候选最多五条，第一条不一定准确；即使只有一条，也请核对后点击确认。</p>
      {error && <p role="alert">{error}</p>}
      {matches && matches.length === 0 && (
        <p role="status">
          没有返回候选地址，请补充城市或更完整的地点名称、地址。
        </p>
      )}
      {matches && matches.length > 0 && (
        <ul className="address-matches">
          {matches.map((match, index) => (
            <li key={`${index}-${match.location.lat}-${match.location.lng}`}>
              <button
                type="button"
                disabled={disabled || resolving}
                onClick={() => onSelect(match)}
              >
                {match.name && <strong>{match.name}</strong>}
                <span>{match.formatted_address}</span>
                <span>
                  {[match.city, match.district].filter(Boolean).join(" · ") ||
                    "城市/区县信息未提供，请核对地址"}
                </span>
                <span>
                  {match.match_kind === "poi"
                    ? "地点搜索结果"
                    : `地址解析结果 · 精度：${match.level || "未知"}（请核对位置）`}
                </span>
                <span>
                  点击使用该地址查询附近（纬度 {match.location.lat.toFixed(4)}
                  ，经度 {match.location.lng.toFixed(4)}）
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PlaceList({ places }: { places: Place[] }) {
  return (
    <section className="nearby-panel" aria-label="地点列表">
      <h2>地点列表</h2>
      <ul className="place-list">
        {places.map((place) => (
          <li key={place.id} className="place-card">
            <div className="place-top">
              <strong>{place.name}</strong>
              <span className="place-distance">
                {formatDistance(place.distance_m)}
              </span>
            </div>
            <span className="place-meta">
              {categoryLabels[place.category]} ·{" "}
              {businessLabels[place.business_status]} ·{" "}
              {place.data_source === "demo" ? "演示数据" : "实时数据"}
            </span>
            <span>{place.address}</span>
            <span>{place.phone ?? "暂无电话"}</span>
            {place.data_source === "amap" && (
              <a
                className="place-nav"
                href={navigationHref(place)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`在新窗口打开${place.name}的高德导航`}
              >
                在高德地图中导航
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
