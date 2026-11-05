import type { Vlog, VlogFilter, VlogUpdateInput } from "../types/vlog";

const BASE = "/api/v1/vlogs";

async function request<T>(
  path: string,
  method = "GET",
  init?: Omit<RequestInit, "method">,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      method,
      headers: { Accept: "application/json", ...init?.headers },
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

export const vlogClient = {
  async list(filter: VlogFilter): Promise<Vlog[]> {
    const query = new URLSearchParams();
    Object.entries(filter).forEach(([k, v]) => {
      if (v !== undefined) query.set(k, String(v));
    });
    const suffix = query.toString();
    const result = await request<Vlog[]>(suffix ? `?${suffix}` : "");
    if (!Array.isArray(result)) throw new Error("Vlog 列表格式错误。");
    return result;
  },
  async create(
    input: { pet_id: string; occurred_on: string; caption: string | null },
    files: File[],
  ): Promise<Vlog> {
    const data = new FormData();
    data.append("pet_id", input.pet_id);
    data.append("occurred_on", input.occurred_on);
    if (input.caption) data.append("caption", input.caption);
    files.forEach((file) => data.append("files", file));
    return request("", "POST", { body: data });
  },
  async update(id: string, input: VlogUpdateInput): Promise<Vlog> {
    return request(`/${encodeURIComponent(id)}`, "PATCH", {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  async remove(id: string): Promise<void> {
    return request(`/${encodeURIComponent(id)}`, "DELETE");
  },
};
