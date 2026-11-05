import { useEffect, useRef, useState } from "react";
import AMapLoader from "@amap/amap-jsapi-loader";
import { wgs84ToGcj02 } from "../../lib/coords";
import type { GeoLocation, NearbyResponse } from "../../types/nearby";

type Position = [number, number];
type Marker = { on(event: "click", handler: () => void): void };
type MapInstance = {
  on(event: "complete", handler: () => void): void;
  add(markers: Marker[]): void;
  setFitView(
    markers: Marker[],
    immediately: boolean,
    padding: number[],
    maxZoom: number,
  ): void;
  setCenter(position: Position): void;
  destroy(): void;
};
type SDK = {
  Map: new (
    container: HTMLElement,
    options: { center: Position; zoom: number; scrollWheel: boolean },
  ) => MapInstance;
  Marker: new (options: {
    position: Position;
    title: string;
    content: HTMLElement;
    anchor: string;
  }) => Marker;
};

function toMapPosition(location: GeoLocation): Position {
  const { lng, lat } = wgs84ToGcj02(location.lat, location.lng);
  return [lng, lat];
}

export default function NearbyMap({
  result,
  selectedId,
  onSelect,
}: {
  result: NearbyResponse;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const key = import.meta.env.VITE_AMAP_JS_KEY?.trim();
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">(
    "loading",
  );
  const view = useRef<{
    map: MapInstance;
    points: Map<string, { position: Position; pin: HTMLElement }>;
  } | null>(null);

  useEffect(() => {
    const element = container.current;
    if (!key || !element) return;
    const apiKey = key;
    const mapElement = element;

    let active = true;
    let map: MapInstance | undefined;
    function destroy() {
      view.current = null;
      map?.destroy();
      map = undefined;
    }

    function fail() {
      if (!active) return;
      active = false;
      window.clearTimeout(timeout);
      destroy();
      setStatus("failed");
    }

    const timeout = window.setTimeout(fail, 15000);
    Object.assign(window, {
      _AMapSecurityConfig: {
        serviceHost: window.location.origin + "/_AMapService",
      },
    });

    async function initialize() {
      const sdk: SDK = await AMapLoader.load({ key: apiKey, version: "2.0" });
      if (!active) return;
      const center = toMapPosition(result.search_center.location);
      const instance = new sdk.Map(mapElement, {
        center,
        zoom: 14,
        scrollWheel: false,
      });
      map = instance;
      const points = new Map<
        string,
        { position: Position; pin: HTMLElement }
      >();
      function marker(position: Position, title: string, text: string) {
        const pin = document.createElement("span");
        pin.className = "nearby-map-pin";
        pin.textContent = text;
        return {
          pin,
          overlay: new sdk.Marker({
            position,
            title,
            content: pin,
            anchor: "center",
          }),
        };
      }
      const markers = [marker(center, "查询中心", "中心").overlay];
      result.places.forEach((place, index) => {
        const position = toMapPosition(place.location);
        const { pin, overlay } = marker(
          position,
          place.name,
          String(index + 1),
        );
        overlay.on("click", () => onSelect(place.id));
        points.set(place.id, { position, pin });
        markers.push(overlay);
      });
      instance.on("complete", () => {
        if (!active || view.current) return;
        try {
          instance.add(markers);
          if (markers.length > 1)
            instance.setFitView(markers, true, [40, 40, 40, 40], 16);
          view.current = { map: instance, points };
          window.clearTimeout(timeout);
          setStatus("ready");
        } catch {
          fail();
        }
      });
    }
    void initialize().catch(fail);

    return () => {
      active = false;
      window.clearTimeout(timeout);
      destroy();
    };
  }, [key, result, onSelect]);

  useEffect(() => {
    const current = view.current;
    if (!current || status !== "ready") return;
    for (const [id, point] of current.points) {
      point.pin.classList.toggle("active", id === selectedId);
    }
    const selected = selectedId && current.points.get(selectedId);
    if (selected) current.map.setCenter(selected.position);
  }, [selectedId, status]);

  if (!key) return null;
  return (
    <section className="nearby-panel" aria-label="高德地图">
      <h2>高德地图</h2>
      {result.source === "demo" && <p>地图上的编号标记为演示地点。</p>}
      {status === "loading" && <p role="status">正在加载地图…</p>}
      {status === "failed" && (
        <p role="status">地图暂时无法加载，仍可查看地点列表。</p>
      )}
      <div
        className="nearby-map"
        ref={container}
        hidden={status === "failed"}
      />
    </section>
  );
}
