// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import RemindersPage from "../src/pages/RemindersPage";
const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  pets: vi.fn(),
  records: vi.fn(),
}));
vi.mock("../src/api/reminders", () => ({
  reminderClient: mocks,
  usingDemoReminders: false,
}));
vi.mock("../src/api/pets", () => ({
  petClient: { list: mocks.pets },
  usingDemoData: false,
}));
const recordsFlags = vi.hoisted(() => ({ usingDemoRecords: false }));
vi.mock("../src/api/records", () => ({
  recordClient: { list: mocks.records },
  get usingDemoRecords() {
    return recordsFlags.usingDemoRecords;
  },
}));
const item = {
  id: "r1",
  pet_id: null,
  title: "下次驱虫",
  due_on: "2026-01-01",
  source_record_id: null,
  status: "pending" as const,
  due_group: "overdue" as const,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
beforeEach(() => {
  vi.resetAllMocks();
  recordsFlags.usingDemoRecords = false;
  mocks.pets.mockResolvedValue([{ id: "p", name: "豆豆" }]);
  mocks.records.mockResolvedValue([]);
  mocks.list.mockResolvedValue([]);
});
afterEach(cleanup);
it("queries unlinked separately and scopes pet queries", async () => {
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("当前范围暂无提醒。");
  expect(mocks.list).toHaveBeenCalledWith({ unlinked: true });
  fireEvent.change(screen.getByLabelText("宠物范围"), {
    target: { value: "p" },
  });
  await waitFor(() =>
    expect(mocks.list).toHaveBeenLastCalledWith({ pet_id: "p" }),
  );
});
it("creates a reminder with a title and date", async () => {
  mocks.create.mockResolvedValue(item);
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("当前范围暂无提醒。");
  fireEvent.change(screen.getByLabelText("标题"), {
    target: { value: "洗澡提醒" },
  });
  fireEvent.change(screen.getByLabelText("到期日期（上海时区）"), {
    target: { value: "2026-02-01" },
  });
  fireEvent.click(screen.getByText("保存提醒"));
  await screen.findByText("提醒已保存。");
  expect(mocks.create).toHaveBeenCalledWith(
    expect.objectContaining({ title: "洗澡提醒", pet_id: null }),
  );
});
it("completes and deletes a pending reminder", async () => {
  mocks.list.mockResolvedValue([item]);
  mocks.update.mockResolvedValue({
    ...item,
    status: "completed",
    due_group: null,
  });
  mocks.remove.mockResolvedValue(undefined);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("下次驱虫");
  fireEvent.click(screen.getByText("完成"));
  await screen.findByText("已标记完成。");
  expect(mocks.update).toHaveBeenCalledWith("r1", { status: "completed" });
  fireEvent.click(screen.getByText("删除"));
  await screen.findByText("提醒已删除。");
  expect(mocks.remove).toHaveBeenCalledWith("r1");
});
it("validates title and keeps input on save failure", async () => {
  mocks.create.mockRejectedValueOnce(new Error("保存失败"));
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("当前范围暂无提醒。");
  fireEvent.change(screen.getByLabelText("标题"), {
    target: { value: "   " },
  });
  fireEvent.click(screen.getByText("保存提醒"));
  await screen.findByText("标题须为 1–120 个字符。");
  fireEvent.change(screen.getByLabelText("标题"), {
    target: { value: "保留输入" },
  });
  fireEvent.click(screen.getByText("保存提醒"));
  await screen.findByText("保存失败");
  expect((screen.getByLabelText("标题") as HTMLInputElement).value).toBe(
    "保留输入",
  );
});
it("shows query failure rather than empty state and can retry", async () => {
  mocks.list.mockRejectedValueOnce(new Error("查询失败"));
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("查询失败");
  expect(screen.queryByText("当前范围暂无提醒。")).toBeNull();
  fireEvent.click(screen.getByText("重试"));
  await screen.findByText("当前范围暂无提醒。");
});
it("hides source record picker when records are demo but reminders use API", async () => {
  recordsFlags.usingDemoRecords = true;
  render(<RemindersPage onNavigate={() => {}} />);
  await screen.findByText("当前范围暂无提醒。");
  expect(
    screen.getByText(/来源记录需要设置 VITE_RECORD_DATA_SOURCE=api/),
  ).toBeTruthy();
  expect(screen.queryByLabelText("来源记录（可选）")).toBeNull();
});
