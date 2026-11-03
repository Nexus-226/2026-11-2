import { shanghaiToday } from "./records";

export type ReminderStatus = "pending" | "completed" | "cancelled";
export type ReminderDueGroup =
  "overdue" | "today" | "upcoming" | "later" | null;

export interface ReminderInput {
  pet_id: string | null;
  title: string;
  due_on: string;
  source_record_id: string | null;
}

export interface PetReminder extends ReminderInput {
  id: string;
  status: ReminderStatus;
  due_group: ReminderDueGroup;
  created_at: string;
  updated_at: string;
}

export interface ReminderFilter {
  pet_id?: string;
  unlinked?: boolean;
  status?: ReminderStatus;
  from_date?: string;
  to_date?: string;
}

// PATCH 省略不变，null 清空可空字段；status 单独用于完成/取消。
export type ReminderPatch = Partial<ReminderInput> & {
  status?: ReminderStatus;
};

function shanghaiInDays(days: number): string {
  const d = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)!.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

// 与后端 reminder_due_group() 对齐，供演示模式本地计算分组。
export function reminderDueGroup(
  due_on: string,
  status: ReminderStatus,
): ReminderDueGroup {
  if (status !== "pending") return null;
  const today = shanghaiToday();
  if (due_on < today) return "overdue";
  if (due_on === today) return "today";
  if (due_on <= shanghaiInDays(7)) return "upcoming";
  return "later";
}
