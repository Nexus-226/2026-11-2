import type { Pet, PetClient, PetInput } from "../types/pet";
import { normalizePetInput, validOtherSpecies } from "../lib/petSpecies";

const STORAGE_KEY = "pet-agent.demo.pets.v1";

function readDemoPets(): Pet[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return [];
    const parsed: unknown = JSON.parse(saved);
    if (!Array.isArray(parsed)) throw new Error("invalid data");
    const pets: unknown[] = parsed.map((pet: unknown) => {
      if (!pet || typeof pet !== "object") throw new Error("invalid data");
      // Only legacy browser storage may omit this field; API responses must include it.
      return { other_species: null, ...pet };
    });
    if (!pets.every(isPet)) throw new Error("invalid data");
    return pets;
  } catch {
    throw new Error("无法读取本地演示数据，请检查浏览器存储设置。");
  }
}

function writeDemoPets(pets: Pet[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pets));
  } catch {
    throw new Error("无法保存演示数据，请检查浏览器存储空间和权限。");
  }
}

function createId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const demoClient: PetClient = {
  async list() {
    return readDemoPets();
  },
  async create(input) {
    const now = new Date().toISOString();
    const pet: Pet = {
      id: createId(),
      ...normalizePetInput(input),
      created_at: now,
      updated_at: now,
    };
    writeDemoPets([...readDemoPets(), pet]);
    return pet;
  },
  async update(id, input) {
    const pets = readDemoPets();
    const index = pets.findIndex((pet) => pet.id === id);
    if (index < 0) throw new Error("未找到这份宠物资料，请刷新后重试。");
    const updated: Pet = {
      ...pets[index],
      ...normalizePetInput(input),
      updated_at: new Date().toISOString(),
    };
    pets[index] = updated;
    writeDemoPets(pets);
    return updated;
  },
  async remove(id) {
    const pets = readDemoPets();
    if (!pets.some((pet) => pet.id === id))
      throw new Error("未找到这份宠物资料，请刷新后重试。");
    writeDemoPets(pets.filter((pet) => pet.id !== id));
  },
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("无法连接后端，请检查服务是否启动后重试。");
  }

  if (!response.ok) {
    let message = `请求失败（${response.status}），请稍后重试。`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "error" in body) {
        const error = (body as { error?: { message?: unknown } }).error;
        if (typeof error?.message === "string" && error.message.trim())
          message = error.message;
      }
    } catch {
      // Use the status-based message if the server did not send the agreed error format.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("后端返回的数据格式不正确，请联系开发人员。");
  }
}

function isPet(value: unknown): value is Pet {
  if (!value || typeof value !== "object") return false;
  const pet = value as Record<string, unknown>;
  const nullableString = (field: unknown) =>
    field === null || typeof field === "string";
  return (
    typeof pet.id === "string" &&
    typeof pet.name === "string" &&
    (pet.species === "dog" ||
      pet.species === "cat" ||
      pet.species === "other") &&
    validOtherSpecies(pet.other_species) &&
    (pet.species === "other" || pet.other_species === null) &&
    nullableString(pet.breed) &&
    nullableString(pet.birthday) &&
    nullableString(pet.notes) &&
    typeof pet.created_at === "string" &&
    typeof pet.updated_at === "string"
  );
}

function requirePet(value: unknown): Pet {
  if (!isPet(value))
    throw new Error("后端返回的宠物资料格式不符合约定，请联系开发人员。");
  return value;
}

const apiClient: PetClient = {
  async list() {
    const result = await request<unknown>("/api/v1/pets");
    if (!Array.isArray(result) || !result.every(isPet))
      throw new Error("后端返回的宠物列表格式不符合约定，请联系开发人员。");
    return result;
  },
  async create(input) {
    return requirePet(
      await request<unknown>("/api/v1/pets", {
        method: "POST",
        body: JSON.stringify(normalizePetInput(input)),
      }),
    );
  },
  async update(id, input) {
    return requirePet(
      await request<unknown>(`/api/v1/pets/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify(normalizePetInput(input)),
      }),
    );
  },
  remove: (id) =>
    request<void>(`/api/v1/pets/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};

// Select explicitly at startup; real API errors never silently fall back to demo data.
export const usingDemoData = import.meta.env.VITE_PET_DATA_SOURCE !== "api";
export const petClient = usingDemoData ? demoClient : apiClient;
