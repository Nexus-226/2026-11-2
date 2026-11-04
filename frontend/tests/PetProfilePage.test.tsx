// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PetProfilePage from "../src/pages/PetProfilePage";
import type { Pet, PetInput } from "../src/types/pet";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}));
vi.mock("../src/api/pets", () => ({ petClient: mocks, usingDemoData: false }));
const pet: Pet = {
  id: "pet-1",
  name: "团团",
  species: "other",
  other_species: "兔",
  breed: null,
  birthday: null,
  notes: null,
  created_at: "2026-11-04T00:00:00Z",
  updated_at: "2026-11-04T00:00:00Z",
};
const name = () => screen.getByRole("textbox", { name: /宠物名字/ });
const species = () => screen.getByRole("combobox", { name: /宠物类型/ });
const detail = () =>
  screen.getByRole("textbox", { name: /具体物种/ }) as HTMLInputElement;

beforeEach(() => {
  vi.resetAllMocks();
  mocks.list.mockResolvedValue([]);
  mocks.create.mockImplementation(async (input: PetInput) => ({
    ...pet,
    ...input,
  }));
  mocks.update.mockImplementation(async (_id: string, input: PetInput) => ({
    ...pet,
    ...input,
  }));
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("编辑已有档案的名字时，不删除具体物种中后端合法保留的 U+FEFF", async () => {
  const value = "\uFEFF兔\uFEFF";
  mocks.list.mockResolvedValue([{ ...pet, other_species: value }]);
  const user = userEvent.setup();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByRole("textbox", { name: /具体物种/ });
  expect(detail().value).toBe(value);
  await user.clear(name());
  await user.type(name(), "新名字");
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByText("宠物资料已保存。");
  expect(mocks.update).toHaveBeenCalledWith(
    pet.id,
    expect.objectContaining({ name: "新名字", other_species: value }),
  );
  expect(detail().value).toBe(value);
});

it("创建具体物种，展示列表与详情；编辑后刷新重新读取", async () => {
  const user = userEvent.setup();
  const view = render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByText("还没有宠物档案");
  expect(screen.queryByRole("textbox", { name: /具体物种/ })).toBeNull();
  await user.type(name(), "团团");
  await user.selectOptions(species(), "other");
  await user.type(detail(), " 兔 ");
  await user.click(screen.getByRole("button", { name: /创建档案/ }));
  await screen.findByText("宠物资料已创建。");
  expect(mocks.create).toHaveBeenCalledWith(
    expect.objectContaining({ other_species: "兔" }),
  );
  expect(screen.getByRole("button", { name: /团团.*其他（兔）/ })).toBeTruthy();
  expect(detail().value).toBe("兔");
  await user.clear(detail());
  await user.type(detail(), "仓鼠");
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByText("宠物资料已保存。");
  expect(mocks.update).toHaveBeenCalledWith(
    pet.id,
    expect.objectContaining({ other_species: "仓鼠" }),
  );
  mocks.list.mockResolvedValue([{ ...pet, other_species: "仓鼠" }]);
  view.unmount();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByRole("button", { name: /团团.*其他（仓鼠）/ });
  expect(detail().value).toBe("仓鼠");
});

it.each(["dog", "cat"])(
  "切换为 %s 会隐藏、显式清空，切回其他不会恢复旧值",
  async (next) => {
    mocks.list.mockResolvedValue([pet]);
    const user = userEvent.setup();
    render(<PetProfilePage onNavigate={vi.fn()} />);
    await screen.findByDisplayValue("兔");
    await user.selectOptions(species(), next);
    expect(screen.queryByRole("textbox", { name: /具体物种/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: /保存修改/ }));
    await screen.findByText("宠物资料已保存。");
    expect(mocks.update).toHaveBeenCalledWith(
      pet.id,
      expect.objectContaining({ species: next, other_species: null }),
    );
    await user.selectOptions(species(), "other");
    expect(detail().value).toBe("");
  },
);

it("其他允许未填；空白转 null，不强制补填", async () => {
  const user = userEvent.setup();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByText("还没有宠物档案");
  await user.type(name(), "团团");
  await user.selectOptions(species(), "other");
  await user.type(detail(), "   ");
  await user.click(screen.getByRole("button", { name: /创建档案/ }));
  await screen.findByText("宠物资料已创建。");
  expect(mocks.create).toHaveBeenCalledWith(
    expect.objectContaining({ other_species: null }),
  );
  expect(
    screen.getByRole("button", { name: /团团.*其他/ }).textContent,
  ).not.toContain("（");
});

it("非 BMP 50 字符允许保存，51 字符拒绝且保留输入，无 HTML maxlength 提前截断", async () => {
  mocks.list.mockResolvedValue([pet]);
  const user = userEvent.setup();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByDisplayValue("兔");
  expect(detail().getAttribute("maxlength")).toBeNull();
  fireEvent.change(detail(), { target: { value: ` ${"𠮷".repeat(50)} ` } });
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByText("宠物资料已保存。");
  expect(mocks.update).toHaveBeenCalledWith(
    pet.id,
    expect.objectContaining({ other_species: "𠮷".repeat(50) }),
  );
  mocks.update.mockClear();
  fireEvent.change(detail(), { target: { value: "𠮷".repeat(51) } });
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByRole("alert");
  expect(mocks.update).not.toHaveBeenCalled();
  expect(detail().value).toBe("𠮷".repeat(51));
});

it("API 保存失败保留输入、不显示成功，可以再次提交", async () => {
  mocks.list.mockResolvedValue([pet]);
  mocks.update.mockRejectedValueOnce(new Error("后端尚未开放字段"));
  const user = userEvent.setup();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByDisplayValue("兔");
  await user.clear(detail());
  await user.type(detail(), "仓鼠");
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByText("后端尚未开放字段");
  expect(detail().value).toBe("仓鼠");
  expect(screen.queryByText("宠物资料已保存。")).toBeNull();
  expect(screen.getByRole("button", { name: /团团.*其他（兔）/ })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /保存修改/ }));
  await screen.findByText("宠物资料已保存。");
  expect(
    screen.getByRole("button", { name: /团团.*其他（仓鼠）/ }),
  ).toBeTruthy();
});

it("切换宠物不残留具体物种，只有具体物种改动也触发未保存确认", async () => {
  mocks.list.mockResolvedValue([
    pet,
    { ...pet, id: "pet-2", name: "豆豆", species: "dog", other_species: null },
  ]);
  const user = userEvent.setup();
  render(<PetProfilePage onNavigate={vi.fn()} />);
  await screen.findByDisplayValue("兔");
  await user.type(detail(), "子");
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await user.click(screen.getByRole("button", { name: /豆豆/ }));
  expect(detail().value).toBe("兔子");
  await user.click(screen.getByRole("button", { name: /豆豆/ }));
  expect(screen.queryByRole("textbox", { name: /具体物种/ })).toBeNull();
  await user.selectOptions(species(), "other");
  expect(detail().value).toBe("");
});
