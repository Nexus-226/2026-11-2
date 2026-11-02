import type { ChatResponse, NearbyResponse, Pet } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {...init, headers: {"Content-Type": "application/json", ...init?.headers}});
  if (!response.ok) throw new Error((await response.text()) || `Request failed: ${response.status}`);
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  listPets: () => request<Pet[]>("/api/v1/pets?user_id=demo-user"),
  createPet: (pet: Omit<Pet, "id">) => request<Pet>("/api/v1/pets", {method: "POST", body: JSON.stringify(pet)}),
  chat: (message: string, petId?: string) => request<ChatResponse>("/api/v1/chat", {method: "POST", body: JSON.stringify({user_id: "demo-user", message, pet_id: petId || null})}),
  nearbyByAddress: (address: string) => request<NearbyResponse>(`/api/v1/nearby?user_id=demo-user&address=${encodeURIComponent(address)}`),
};
