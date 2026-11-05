// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AppScopeProvider, useAppScope } from "../src/app/AppScope";
import RecordsPage from "../src/pages/RecordsPage";
import type { RecordDraft } from "../src/types/records";

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

function DraftHarness({ draft }: { draft: RecordDraft }) {
  const scope = useAppScope()!;
  useEffect(() => {
    scope.openRecordDraft(draft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <RecordsPage onNavigate={() => {}} />;
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.pets.mockResolvedValue([{ id: "p", name: "豆豆" }]);
  mocks.list.mockResolvedValue([]);
  mocks.create.mockResolvedValue({
    id: "r",
    pet_id: "p",
    record_type: "bath",
    occurred_on: "2026-01-01",
    name: null,
    weight_kg: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  });
  Object.defineProperty(window, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  });
});
afterEach(cleanup);

it("从聊天草稿打开预填的洗澡记录表单并保存到草稿宠物", async () => {
  render(
    <AppScopeProvider>
      <DraftHarness
        draft={{
          record_type: "bath",
          occurred_on: "2026-01-01",
          pet_id: "p",
          name: null,
          notes: null,
        }}
      />
    </AppScopeProvider>,
  );

  await waitFor(() =>
    expect((screen.getByLabelText("护理类型") as HTMLSelectElement).value).toBe(
      "bath",
    ),
  );
  expect(
    (screen.getByLabelText("发生日期（上海时区）") as HTMLInputElement).value,
  ).toBe("2026-01-01");

  fireEvent.click(screen.getByRole("button", { name: "保存记录" }));
  await waitFor(() =>
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        record_type: "bath",
        occurred_on: "2026-01-01",
        pet_id: "p",
      }),
    ),
  );
});
