export type RecordType = "vaccine" | "deworming" | "bath" | "weight";
export interface RecordInput {
  pet_id: string | null;
  record_type: RecordType;
  occurred_on: string;
  name: string | null;
  weight_kg: number | null;
  notes: string | null;
}
export interface PetRecord extends RecordInput {
  id: string;
  created_at: string;
  updated_at: string;
}
export interface RecordFilter {
  pet_id?: string;
  unlinked?: boolean;
  record_type?: RecordType;
  from_date?: string;
  to_date?: string;
}
// P2：聊天响应里的洗澡记录草稿；只用于预填记录表单，不代表已保存。
export interface RecordDraft {
  record_type: "bath";
  occurred_on: string;
  pet_id: string;
  name: string | null;
  notes: string | null;
}
export function shanghaiToday() {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (t: string) => parts.find((p) => p.type === t)!.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
