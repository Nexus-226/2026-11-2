// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import RecordsPage from "../src/pages/RecordsPage";
const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  pets: vi.fn(),
}));
vi.mock("../src/api/records", () => ({
  recordClient: mocks,
  usingDemoRecords: false,
}));
vi.mock("../src/api/pets", () => ({
  petClient: { list: mocks.pets },
  usingDemoData: false,
}));
const item = {
  id: "r",
  pet_id: null,
  record_type: "weight",
  occurred_on: "2026-01-01",
  name: null,
  weight_kg: 4.25,
  notes: "原备注",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
beforeEach(() => {
  vi.resetAllMocks();
  mocks.pets.mockResolvedValue([{ id: "p", name: "豆豆" }]);
  mocks.list.mockResolvedValue([]);
});
afterEach(cleanup);
it("queries unlinked separately and explicitly scopes pet queries", async () => {
  render(<RecordsPage onNavigate={() => {}} />);
  await screen.findByText("当前筛选下暂无记录。");
  expect(mocks.list).toHaveBeenCalledWith({ unlinked: true });
  fireEvent.change(screen.getByLabelText("宠物范围"), {
    target: { value: "p" },
  });
  await waitFor(() =>
    expect(mocks.list).toHaveBeenLastCalledWith({ pet_id: "p" }),
  );
});
it("keeps input on failure and clears weight when changing record type", async () => {
  mocks.create
    .mockRejectedValueOnce(new Error("保存失败"))
    .mockResolvedValue(item);
  render(<RecordsPage onNavigate={() => {}} />);
  await screen.findByText("当前筛选下暂无记录。");
  fireEvent.change(screen.getByLabelText("护理类型"), {
    target: { value: "weight" },
  });
  fireEvent.change(screen.getByLabelText("体重（kg）"), {
    target: { value: "4.25" },
  });
  fireEvent.change(screen.getByLabelText("备注"), {
    target: { value: "保留输入" },
  });
  fireEvent.click(screen.getByText("保存记录"));
  await screen.findByText("保存失败");
  expect((screen.getByLabelText("备注") as HTMLTextAreaElement).value).toBe(
    "保留输入",
  );
  fireEvent.change(screen.getByLabelText("护理类型"), {
    target: { value: "bath" },
  });
  fireEvent.click(screen.getByText("保存记录"));
  await screen.findByText("记录已保存。");
  expect(mocks.create.mock.calls[1][0]).toMatchObject({
    record_type: "bath",
    weight_kg: null,
    pet_id: null,
  });
});
it("edits and deletes structured weight records", async () => {
  mocks.list.mockResolvedValue([item]);
  mocks.update.mockResolvedValue(item);
  mocks.remove.mockResolvedValue(undefined);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<RecordsPage onNavigate={() => {}} />);
  await screen.findByText("体重 · 4.25 kg");
  fireEvent.click(screen.getByText("编辑"));
  fireEvent.change(screen.getByLabelText("体重（kg）"), {
    target: { value: "5" },
  });
  fireEvent.click(screen.getByText("保存记录"));
  await screen.findByText("记录已保存。");
  expect(mocks.update).toHaveBeenCalledWith(
    "r",
    expect.objectContaining({ weight_kg: 5 }),
  );
  fireEvent.click(screen.getByText("删除"));
  await screen.findByText("记录已删除。");
  expect(mocks.remove).toHaveBeenCalledWith("r");
});
it("shows query failure rather than empty state and can retry", async () => {
  mocks.list.mockRejectedValueOnce(new Error("查询失败"));
  render(<RecordsPage onNavigate={() => {}} />);
  await screen.findByText("查询失败");
  expect(screen.queryByText("当前筛选下暂无记录。")).toBeNull();
  fireEvent.click(screen.getByText("重试"));
  await screen.findByText("当前筛选下暂无记录。");
});
