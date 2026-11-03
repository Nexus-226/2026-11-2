export type NearbyCategory = "pet_hospital" | "pet_grooming" | "pet_store";
export type CenterSource = "user_location" | "resolved_address" | "demo_region";
export type NearbyDataSource = "amap" | "demo";
export type FallbackReason = "amap_unavailable" | "amap_not_configured" | null;
export type BusinessStatus = "open" | "closed" | "unknown";
export interface GeoLocation {
  lat: number;
  lng: number;
}
export interface SearchCenter {
  location: GeoLocation;
  source: CenterSource;
  label: string;
}
export interface Place {
  id: string;
  name: string;
  category: NearbyCategory;
  address: string;
  phone: string | null;
  location: GeoLocation;
  distance_m: number;
  business_status: BusinessStatus;
  navigation_url: string | null;
  data_source: NearbyDataSource;
}
export interface NearbyResponse {
  places: Place[];
  search_center: SearchCenter;
  source: NearbyDataSource;
  fallback_reason: FallbackReason;
}
export interface AddressMatch {
  formatted_address: string;
  location: GeoLocation;
  data_source: "amap";
}
