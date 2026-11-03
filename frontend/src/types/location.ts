import type { GeoLocation } from "./nearby";

/** 单条地址解析候选（对应 POST /api/v1/locations/resolve 的 matches 项）。 */
export interface AddressMatch {
  formatted_address: string;
  location: GeoLocation;
  data_source: "amap";
}
