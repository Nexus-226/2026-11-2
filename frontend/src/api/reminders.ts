import type {
  PetReminder,
  ReminderFilter,
  ReminderInput,
  ReminderPatch,
} from "../types/reminders";
import { reminderDueGroup } from "../types/reminders";

export const usingDemoReminders =
  import.meta.env.VITE_REMINDER_DATA_SOURCE !== "api";
const key = "pet-agent.demo.reminders.v1";

function read(): PetReminder[] {
  try {
    const data = JSON.parse(localStorage.getItem(key) ?? "[]");
    if (!Array.isArray(data)) throw new Error();
    return data;
  } catch {
    throw new Error("无法读取本地演示提醒。");
  }
}

function write(items: PetReminder[]) {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch {
    throw new Error("本地演示提醒保存失败。");
  }
}

const sort = (items: PetReminder[]) =>
  [...items].sort(
    (a, b) =>
      a.due_on.localeCompare(b.due_on) ||
      a.created_at.localeCompare(b.created_at) ||
      a.id.localeCompare(b.id),
  );

async function request<T>(
  path: string,
  method = "GET",
  input?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/reminders${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(input !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(input !== undefined ? { body: JSON.stringify(input) } : {}),
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

export const reminderClient = {
  async list(filter: ReminderFilter): Promise<PetReminder[]> {
    if (usingDemoReminders)
      return sort(
        read()
          .map((r) => ({
            ...r,
            due_group: reminderDueGroup(r.due_on, r.status),
          }))
          .filter(
            (r) =>
              (!filter.pet_id || r.pet_id === filter.pet_id) &&
              (!filter.unlinked || r.pet_id === null) &&
              (!filter.status || r.status === filter.status) &&
              (!filter.from_date || r.due_on >= filter.from_date) &&
              (!filter.to_date || r.due_on <= filter.to_date),
          ),
      );
    const query = new URLSearchParams();
    Object.entries(filter).forEach(([k, v]) => {
      if (v !== undefined) query.set(k, String(v));
    });
    const result = await request<PetReminder[]>(`?${query}`);
    if (!Array.isArray(result)) throw new Error("提醒列表格式错误。");
    return sort(result);
  },
  async create(input: ReminderInput): Promise<PetReminder> {
    if (!usingDemoReminders) return request("", "POST", input);
    const now = new Date().toISOString();
    const item: PetReminder = {
      ...input,
      id: crypto.randomUUID(),
      status: "pending",
      due_group: reminderDueGroup(input.due_on, "pending"),
      created_at: now,
      updated_at: now,
    };
    write([...read(), item]);
    return item;
  },
  async update(id: string, patch: ReminderPatch): Promise<PetReminder> {
    if (!usingDemoReminders)
      return request(`/${encodeURIComponent(id)}`, "PATCH", patch);
    const items = read();
    const old = items.find((r) => r.id === id);
    if (!old) throw new Error("提醒不存在，请刷新。");
    if (
      patch.status &&
      old.status !== "pending" &&
      patch.status !== old.status
    ) {
      throw new Error("已完成或已取消的提醒不能重新开启。");
    }
    const merged: PetReminder = {
      ...old,
      ...patch,
      due_group: reminderDueGroup(
        patch.due_on ?? old.due_on,
        patch.status ?? old.status,
      ),
      updated_at: new Date().toISOString(),
    };
    write(items.map((r) => (r.id === id ? merged : r)));
    return merged;
  },
  async remove(id: string): Promise<void> {
    if (!usingDemoReminders)
      return request(`/${encodeURIComponent(id)}`, "DELETE");
    write(read().filter((r) => r.id !== id));
  },
};
