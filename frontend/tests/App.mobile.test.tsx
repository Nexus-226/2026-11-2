// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../src/app/App";
import type { Pet } from "../src/types/pet";
import type {
  PetRecord,
  RecordFilter,
  RecordInput,
} from "../src/types/records";
const m = vi.hoisted(() => ({
  pets: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  records: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  reminders: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
  chat: { send: vi.fn() },
  mode: { demoPets: false },
}));
vi.mock("../src/api/pets", () => ({
  petClient: m.pets,
  get usingDemoData() {
    return m.mode.demoPets;
  },
}));
vi.mock("../src/api/records", () => ({
  recordClient: m.records,
  usingDemoRecords: false,
}));
vi.mock("../src/api/reminders", () => ({
  reminderClient: m.reminders,
  usingDemoReminders: false,
}));
vi.mock("../src/api/chat", () => ({
  chatClient: m.chat,
  usingDemoChat: false,
}));
const cat: Pet = {
  id: "cat",
  name: "豆豆",
  species: "cat",
  other_species: null,
  breed: "英短",
  birthday: "2023-03-18",
  notes: null,
  created_at: "",
  updated_at: "",
};
const dog: Pet = { ...cat, id: "dog", species: "dog", breed: "柴犬" };
const row = (id: string, pet: string, weight: number): PetRecord => ({
  id,
  pet_id: pet,
  record_type: "weight",
  occurred_on: "2026-11-01",
  weight_kg: weight,
  name: null,
  notes: null,
  created_at: "2026-11-01T00:00:00Z",
  updated_at: "",
});
const nav = (label: string) =>
  within(screen.getByRole("navigation", { name: "底部导航" })).getByRole(
    "button",
    { name: label, exact: true },
  );
async function choose(breed: string) {
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: /当前宠物：.*点击切换/ })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: /当前宠物：.*点击切换/ }));
  fireEvent.click(
    screen.getByRole("radio", { name: new RegExp(`豆豆.*${breed}`) }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "确认切换", exact: true }),
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  m.mode.demoPets = false;
  m.pets.list.mockResolvedValue([cat, dog]);
  m.records.list.mockImplementation(async (f: RecordFilter) =>
    [row("c", "cat", 5), row("d", "dog", 13)].filter(
      (r) =>
        (!f.pet_id || r.pet_id === f.pet_id) &&
        (!f.unlinked || r.pet_id === null),
    ),
  );
  m.records.create.mockImplementation(async (input: RecordInput) => ({
    ...input,
    id: "new-record",
    created_at: "",
    updated_at: "",
  }));
  m.reminders.list.mockResolvedValue([]);
  m.chat.send.mockResolvedValue({
    session_id: "session-one",
    message_id: "msg",
    reply: "模拟接口回复",
    tool_calls: [],
  });
  m.pets.create.mockImplementation(async (input) => ({
    ...input,
    id: "new-pet",
    created_at: "",
    updated_at: "",
  }));
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  HTMLElement.prototype.scrollIntoView = vi.fn();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("keeps the selected pet across record/reminder/profile pages and family members are display-only", async () => {
  render(<App />);
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: /当前宠物：未关联宠物/ })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  await choose("英短");
  fireEvent.click(nav("记录"));
  await waitFor(() =>
    expect(m.records.list).toHaveBeenCalledWith(
      expect.objectContaining({ pet_id: "cat" }),
    ),
  );
  expect(
    screen.getByRole("button", { name: /当前宠物：豆豆 · 英短/ }),
  ).toBeTruthy();
  fireEvent.click(nav("待办"));
  await waitFor(() =>
    expect(m.reminders.list).toHaveBeenCalledWith({ pet_id: "cat" }),
  );
  fireEvent.click(nav("我的"));
  expect(
    within(screen.getByRole("region", { name: "我的宠物家庭" }))
      .queryAllByRole("button")
      .map((e) => e.textContent),
  ).toEqual(["＋ 新增宠物"]);
  fireEvent.click(screen.getByRole("button", { name: /宠物档案.*查看与编辑/ }));
  expect(
    await screen.findByRole("button", { name: "编辑资料", exact: true }),
  ).toBeTruthy();
  expect(screen.queryByRole("textbox", { name: /宠物名字/ })).toBeNull();
});
it("cancelling a pet switch preserves a record draft and accepts only after confirmation", async () => {
  render(<App />);
  await waitFor(() => expect(m.pets.list).toHaveBeenCalled());
  await choose("英短");
  fireEvent.click(nav("记录"));
  fireEvent.click(
    screen.getByRole("button", { name: "＋ 添加记录", exact: true }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "项目或产品名称" }), {
    target: { value: "未保存记录" },
  });
  vi.mocked(window.confirm).mockReturnValue(false);
  await choose("柴犬");
  expect(
    screen
      .getByRole("textbox", { name: "项目或产品名称" })
      .getAttribute("value"),
  ).toBe("未保存记录");
  expect(
    screen.getByRole("button", { name: /当前宠物：豆豆 · 英短/ }),
  ).toBeTruthy();
  vi.mocked(window.confirm).mockReturnValue(true);
  fireEvent.click(
    screen.getByRole("button", { name: "确认切换", exact: true }),
  );
  await waitFor(() =>
    expect(m.records.list).toHaveBeenCalledWith(
      expect.objectContaining({ pet_id: "dog" }),
    ),
  );
  expect(
    screen
      .getByRole("textbox", { name: "项目或产品名称" })
      .getAttribute("value"),
  ).toBe("");
});
it("a switch from another page resets chat session and never submits the previous pet id", async () => {
  render(<App />);
  await waitFor(() => expect(m.pets.list).toHaveBeenCalled());
  await choose("英短");
  const input = screen.getByPlaceholderText("输入你想问的问题…");
  fireEvent.change(input, { target: { value: "第一次问题" } });
  fireEvent.click(screen.getByRole("button", { name: /发送/ }));
  await screen.findByText("模拟接口回复");
  expect(m.chat.send.mock.calls[0][0]).toEqual({
    message: "第一次问题",
    pet_id: "cat",
    session_id: null,
  });
  fireEvent.click(nav("记录"));
  await choose("柴犬");
  expect(window.confirm).toHaveBeenCalledWith(
    expect.stringContaining("开始新对话"),
  );
  fireEvent.click(nav("助手"));
  expect(screen.queryByText("第一次问题")).toBeNull();
  fireEvent.change(screen.getByPlaceholderText("输入你想问的问题…"), {
    target: { value: "第二次问题" },
  });
  fireEvent.click(screen.getByRole("button", { name: /发送/ }));
  await waitFor(() => expect(m.chat.send).toHaveBeenCalledTimes(2));
  expect(m.chat.send.mock.calls[1][0]).toEqual({
    message: "第二次问题",
    pet_id: "dog",
    session_id: null,
  });
});
it("real record and reminder clients never receive ids from demo pets", async () => {
  m.mode.demoPets = true;
  render(<App />);
  await waitFor(() => expect(m.pets.list).toHaveBeenCalled());
  fireEvent.click(nav("我的"));
  await choose("英短");
  fireEvent.click(nav("记录"));
  await waitFor(() => expect(m.records.list).toHaveBeenCalled());
  expect(
    m.records.list.mock.calls.every(([f]) => f.unlinked === true && !f.pet_id),
  ).toBe(true);
  fireEvent.click(nav("待办"));
  await waitFor(() => expect(m.reminders.list).toHaveBeenCalled());
  expect(
    m.reminders.list.mock.calls.every(
      ([f]) => f.unlinked === true && !f.pet_id,
    ),
  ).toBe(true);
});
it("creates a pet with the original payload and shows its profile, not the previous pet", async () => {
  render(<App />);
  await waitFor(() => expect(m.pets.list).toHaveBeenCalled());
  fireEvent.click(nav("我的"));
  fireEvent.click(
    screen.getByRole("button", { name: "＋ 新增宠物", exact: true }),
  );
  const input = await screen.findByRole("textbox", { name: /宠物名字/ });
  fireEvent.change(input, { target: { value: "糯米" } });
  fireEvent.change(screen.getByRole("combobox", { name: /宠物类型/ }), {
    target: { value: "other" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: /具体物种/ }), {
    target: { value: "兔" },
  });
  fireEvent.click(screen.getByRole("button", { name: /创建档案/ }));
  await waitFor(() =>
    expect(m.pets.create).toHaveBeenCalledWith({
      name: "糯米",
      species: "other",
      other_species: "兔",
      breed: null,
      birthday: null,
      notes: null,
    }),
  );
  expect(
    await screen.findByRole("button", { name: /当前宠物：糯米/ }),
  ).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "编辑资料", exact: true }),
  ).toBeTruthy();
});
it("supports creating a reminder with the existing title/date/source contract", async () => {
  m.reminders.create.mockResolvedValue({ id: "new-todo" });
  render(<App />);
  await waitFor(() => expect(m.pets.list).toHaveBeenCalled());
  await choose("英短");
  fireEvent.click(nav("待办"));
  fireEvent.click(
    screen.getByRole("button", { name: "＋ 创建待办", exact: true }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: /标题/ }), {
    target: { value: "下次称重" },
  });
  const source = screen.getByRole("combobox", { name: /来源记录/ });
  await waitFor(() =>
    expect(source.querySelectorAll("option").length).toBeGreaterThan(1),
  );
  fireEvent.change(source, { target: { value: "c" } });
  fireEvent.click(
    screen.getByRole("button", { name: "保存提醒", exact: true }),
  );
  await waitFor(() =>
    expect(m.reminders.create).toHaveBeenCalledWith(
      expect.objectContaining({
        pet_id: "cat",
        title: "下次称重",
        source_record_id: "c",
      }),
    ),
  );
  expect(Object.keys(m.reminders.create.mock.calls[0][0]).sort()).toEqual([
    "due_on",
    "pet_id",
    "source_record_id",
    "title",
  ]);
});

it("late pet loading preserves an unsent question and never silently associates a pet", async () => {
  let resolve!: (pets: Pet[]) => void;
  m.pets.list.mockImplementationOnce(
    () =>
      new Promise<Pet[]>((done) => {
        resolve = done;
      }),
  );
  render(<App />);
  fireEvent.change(screen.getByPlaceholderText("输入你想问的问题…"), {
    target: { value: "不要清空的问题" },
  });
  resolve([cat, dog]);
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: /当前宠物：未关联宠物/ })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  expect(
    (screen.getByPlaceholderText("输入你想问的问题…") as HTMLTextAreaElement)
      .value,
  ).toBe("不要清空的问题");
});
it("blocks navigation while a real chat request is pending and unlocks after cancellation", async () => {
  m.chat.send.mockImplementation(
    (_request, signal: AbortSignal) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener(
          "abort",
          () => reject(new DOMException("cancelled", "AbortError")),
          { once: true },
        ),
      ),
  );
  render(<App />);
  await choose("英短");
  fireEvent.change(screen.getByPlaceholderText("输入你想问的问题…"), {
    target: { value: "等待中的问题" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送", exact: true }));
  await waitFor(() => expect(m.chat.send).toHaveBeenCalledTimes(1));
  fireEvent.click(nav("记录"));
  expect(screen.queryByRole("heading", { name: /^日常记录/ })).toBeNull();
  expect(screen.getByText(/当前操作尚未结束/)).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "停止等待", exact: true }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "停止等待", exact: true }),
    ).toBeNull(),
  );
  fireEvent.click(nav("记录"));
  expect(screen.getByRole("heading", { name: /^日常记录/ })).toBeTruthy();
});
it("failed record saves keep the draft and expose the original API error", async () => {
  m.records.create.mockRejectedValueOnce(new Error("模拟服务端拒绝保存"));
  render(<App />);
  await choose("英短");
  fireEvent.click(nav("记录"));
  fireEvent.click(
    screen.getByRole("button", { name: "＋ 添加记录", exact: true }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "项目或产品名称" }), {
    target: { value: "请保留的草稿" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "保存记录", exact: true }),
  );
  expect(await screen.findByText("模拟服务端拒绝保存")).toBeTruthy();
  expect(
    (
      screen.getByRole("textbox", {
        name: "项目或产品名称",
      }) as HTMLInputElement
    ).value,
  ).toBe("请保留的草稿");
  vi.mocked(window.confirm).mockReturnValue(false);
  fireEvent.click(nav("我的"));
  expect(screen.getByRole("heading", { name: /^日常记录/ })).toBeTruthy();
});
