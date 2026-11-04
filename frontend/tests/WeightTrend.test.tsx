// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import WeightTrend from "../src/components/common/WeightTrend";
import type { PetRecord } from "../src/types/records";
const { list } = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("../src/api/records", () => ({
  recordClient: { list },
  usingDemoRecords: false,
}));
const record = (
  id: string,
  date: string,
  weight: number,
  pet = "p",
): PetRecord => ({
  id,
  pet_id: pet,
  record_type: "weight",
  occurred_on: date,
  weight_kg: weight,
  name: null,
  notes: null,
  created_at: `2026-11-01T00:00:0${id}Z`,
  updated_at: "",
});
const props = { petId: "p", petName: "豆豆", revision: 0, onAdd: vi.fn() };
beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-04T00:00:00Z"));
  list.mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
it("does not query or mix unlinked records and offers add when empty", async () => {
  const view = render(<WeightTrend {...props} petId={null} />);
  expect(list).not.toHaveBeenCalled();
  view.rerender(<WeightTrend {...props} />);
  await screen.findByText("所选时间范围内暂无体重记录。");
  fireEvent.click(screen.getByText("添加体重记录"));
  expect(props.onAdd).toHaveBeenCalled();
  expect(list).toHaveBeenCalledWith({
    pet_id: "p",
    record_type: "weight",
    from_date: "2026-08-07",
    to_date: "2026-11-04",
  });
});
it("renders a single point and keeps same-day readings, sorting dates and isolating pets", async () => {
  list.mockResolvedValue([record("1", "2026-11-01", 4)]);
  const view = render(<WeightTrend {...props} />);
  await screen.findByText("再记录一次即可查看变化。");
  expect(
    screen.getAllByRole("button", { name: /2026-11-01，4 kg/ }),
  ).toHaveLength(1);
  list.mockResolvedValue([
    record("3", "2026-11-04", 4.4),
    record("2", "2026-11-04", 4.3),
    record("1", "2026-11-01", 4),
    record("4", "2026-11-04", 99, "other"),
  ]);
  view.rerender(<WeightTrend {...props} revision={1} />);
  await screen.findByText("3 条称重记录");
  expect(screen.queryByText("再记录一次即可查看变化。")).toBeNull();
  expect(screen.queryByRole("button", { name: /99 kg/ })).toBeNull();
  expect(screen.getByText("+0.4 kg")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "2026-11-04，4.3 kg" }));
  expect(screen.getByText("选中记录：2026-11-04 · 4.3 kg")).toBeTruthy();
  fireEvent.click(screen.getByText("近30天"));
  await waitFor(() =>
    expect(list).toHaveBeenLastCalledWith(
      expect.objectContaining({ from_date: "2026-10-06" }),
    ),
  );
  fireEvent.click(screen.getByText("全部"));
  await waitFor(() =>
    expect(list).toHaveBeenLastCalledWith({
      pet_id: "p",
      record_type: "weight",
      to_date: "2026-11-04",
    }),
  );
});
it("ignores late replies across pets and reports failures separately from empty results", async () => {
  let resolve!: (items: PetRecord[]) => void;
  list
    .mockImplementationOnce(
      () =>
        new Promise<PetRecord[]>((r) => {
          resolve = r;
        }),
    )
    .mockRejectedValueOnce(new Error("连接失败"));
  const view = render(<WeightTrend {...props} />);
  expect(screen.getByText("正在加载体重趋势…")).toBeTruthy();
  view.rerender(<WeightTrend {...props} petId="other" petName="团团" />);
  await screen.findByRole("alert");
  resolve([record("1", "2026-11-01", 4)]);
  expect(screen.queryByText("所选时间范围内暂无体重记录。")).toBeNull();
  fireEvent.click(screen.getByText("重试体重趋势"));
  await screen.findByText("所选时间范围内暂无体重记录。");
  expect(screen.queryByRole("img")).toBeNull();
});
