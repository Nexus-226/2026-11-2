import type { PetRecord, RecordInput, RecordFilter } from "../types/records";
export const usingDemoRecords =
  import.meta.env.VITE_RECORD_DATA_SOURCE !== "api";
const key = "pet-agent.demo.records.v1";
function read(): PetRecord[] {
  try {
    const data = JSON.parse(localStorage.getItem(key) ?? "[]");
    if (!Array.isArray(data)) throw new Error();
    return data;
  } catch {
    throw new Error("无法读取本地演示记录。");
  }
}
function write(items: PetRecord[]) {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch {
    throw new Error("本地演示记录保存失败。");
  }
}
const sort = (items: PetRecord[]) =>
  [...items].sort(
    (a, b) =>
      b.occurred_on.localeCompare(a.occurred_on) ||
      b.created_at.localeCompare(a.created_at) ||
      a.id.localeCompare(b.id),
  );
async function request<T>(
  path: string,
  method = "GET",
  input?: RecordInput,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/records${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(input ? { "Content-Type": "application/json" } : {}),
      },
      ...(input ? { body: JSON.stringify(input) } : {}),
    });
  } catch {
    throw new Error("无法连接后端，请检查服务后重试。");
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (typeof body?.error?.message === "string")
        message = body.error.message;
    } catch {
      /* status fallback */
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const recordClient = {
  async list(filter: RecordFilter): Promise<PetRecord[]> {
    if (usingDemoRecords)
      return sort(
        read().filter(
          (r) =>
            (!filter.pet_id || r.pet_id === filter.pet_id) &&
            (!filter.unlinked || r.pet_id === null) &&
            (!filter.record_type || r.record_type === filter.record_type) &&
            (!filter.from_date || r.occurred_on >= filter.from_date) &&
            (!filter.to_date || r.occurred_on <= filter.to_date),
        ),
      );
    const query = new URLSearchParams();
    Object.entries(filter).forEach(([k, v]) => {
      if (v !== undefined) query.set(k, String(v));
    });
    const result = await request<PetRecord[]>(`?${query}`);
    if (!Array.isArray(result)) throw new Error("记录列表格式错误。");
    return sort(result);
  },
  async create(input: RecordInput): Promise<PetRecord> {
    if (!usingDemoRecords) return request("", "POST", input);
    const now = new Date().toISOString();
    const item = {
      ...input,
      id: crypto.randomUUID(),
      created_at: now,
      updated_at: now,
    };
    write([...read(), item]);
    return item;
  },
  async update(id: string, input: RecordInput): Promise<PetRecord> {
    if (!usingDemoRecords)
      return request(`/${encodeURIComponent(id)}`, "PATCH", input);
    const items = read();
    const old = items.find((r) => r.id === id);
    if (!old) throw new Error("记录不存在，请刷新。");
    const item = { ...old, ...input, updated_at: new Date().toISOString() };
    write(items.map((r) => (r.id === id ? item : r)));
    return item;
  },
  async remove(id: string): Promise<void> {
    if (!usingDemoRecords)
      return request(`/${encodeURIComponent(id)}`, "DELETE");
    write(read().filter((r) => r.id !== id));
  },
};
