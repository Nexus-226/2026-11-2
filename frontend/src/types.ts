export type Pet = {
  id: string; user_id: "demo-user"; name: string; species: string; breed?: string | null;
  age_years?: number | null; health_notes?: string | null;
};

export type ToolResult = {
  tool: string; status: "success" | "not_found" | "invalid_input" | "unavailable" | "error"; message?: string | null;
};

export type ChatResponse = {
  request_id: string; session_id: string; reply: string; used_pet_id?: string | null; tool_results: ToolResult[];
};

export type NearbyResponse = {
  places: Array<{id: string; name: string; category: "pet_hospital" | "pet_grooming" | "pet_store"; address: string; distance_m: number; data_source: string}>;
  coordinate_converted: boolean; location_source: "browser" | "manual_address_mock";
};
