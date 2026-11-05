// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import VlogPage from "../src/pages/VlogPage";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  pets: vi.fn(),
}));
vi.mock("../src/api/vlogs", () => ({ vlogClient: mocks }));
vi.mock("../src/api/pets", () => ({
  petClient: { list: mocks.pets },
  usingDemoData: false,
}));

const vlog = {
  id: "v1",
  pet_id: "p",
  caption: "公园散步",
  occurred_on: "2026-01-01",
  media: [
    {
      id: "m1",
      media_type: "image",
      filename: "a.png",
      content_type: "image/png",
      size_bytes: 10,
      url: "/api/v1/vlogs/media/abcd.png",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function pngFile(name = "a.png") {
  return new File([new Uint8Array([1, 2, 3])], name, { type: "image/png" });
}

function mp4File() {
  return new File([new Uint8Array([4])], "b.mp4", { type: "video/mp4" });
}

function attachFiles(files: File[]) {
  const input = screen.getByLabelText(/媒体（选传/);
  Object.defineProperty(input, "files", { value: files, configurable: true });
  fireEvent.change(input);
}

async function selectPet() {
  await screen.findByText("选择宠物后查看它的 Vlog 时间线。");
  fireEvent.change(screen.getByLabelText("当前宠物"), {
    target: { value: "p" },
  });
}

async function openForm() {
  await selectPet();
  await screen.findByText("豆豆的时间线");
  fireEvent.click(screen.getByText("＋ 新建 Vlog"));
  await screen.findByText("保存 Vlog");
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.pets.mockResolvedValue([{ id: "p", name: "豆豆" }]);
  mocks.list.mockResolvedValue([]);
});

afterEach(cleanup);

it("lists the selected pet's timeline with media", async () => {
  mocks.list.mockResolvedValue([vlog]);
  render(<VlogPage onNavigate={() => {}} />);
  await screen.findByText("选择宠物后查看它的 Vlog 时间线。");
  expect(mocks.list).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("当前宠物"), {
    target: { value: "p" },
  });
  await screen.findByText("豆豆的时间线");
  await screen.findByText("公园散步");
  const img = screen.getByAltText("a.png");
  expect(img.getAttribute("src")).toBe("/api/v1/vlogs/media/abcd.png");
  expect(mocks.list).toHaveBeenCalledWith({ pet_id: "p" });
});

it("creates a vlog with caption and media files", async () => {
  mocks.create.mockResolvedValue(vlog);
  render(<VlogPage onNavigate={() => {}} />);
  await openForm();
  fireEvent.change(screen.getByLabelText("日期"), {
    target: { value: "2026-01-02" },
  });
  fireEvent.change(screen.getByLabelText("文案"), {
    target: { value: "  第一次洗澡  " },
  });
  attachFiles([pngFile()]);
  fireEvent.click(screen.getByText("保存 Vlog"));
  await screen.findByText("Vlog 已保存。");
  expect(mocks.create).toHaveBeenCalledTimes(1);
  const [input, files] = mocks.create.mock.calls[0];
  expect(input).toEqual({
    pet_id: "p",
    occurred_on: "2026-01-02",
    caption: "第一次洗澡",
  });
  expect(files).toHaveLength(1);
  expect(files[0].name).toBe("a.png");
  expect(mocks.list).toHaveBeenCalledWith({ pet_id: "p" });
});

it("rejects mixed media client-side before uploading", async () => {
  render(<VlogPage onNavigate={() => {}} />);
  await openForm();
  attachFiles([pngFile(), mp4File()]);
  fireEvent.click(screen.getByText("保存 Vlog"));
  await screen.findByText("同一篇只能全部是图片或是一段视频，不能混合。");
  expect(mocks.create).not.toHaveBeenCalled();
});

it("edits caption and date without touching media", async () => {
  mocks.list.mockResolvedValue([vlog]);
  mocks.update.mockResolvedValue(vlog);
  render(<VlogPage onNavigate={() => {}} />);
  await selectPet();
  await screen.findByText("公园散步");
  vi.spyOn(window, "confirm").mockReturnValue(true);
  fireEvent.click(screen.getByText("编辑"));
  await screen.findByText(
    "首版不支持替换媒体；如需更换，请删除这篇后重新创建。",
  );
  fireEvent.change(screen.getByLabelText("文案"), {
    target: { value: "改成在家打盹" },
  });
  fireEvent.click(screen.getByText("保存修改"));
  await screen.findByText("Vlog 已保存。");
  expect(mocks.update).toHaveBeenCalledWith("v1", {
    caption: "改成在家打盹",
    occurred_on: "2026-01-01",
  });
});

it("deletes a vlog after confirmation", async () => {
  mocks.list.mockResolvedValue([vlog]);
  mocks.remove.mockResolvedValue(undefined);
  render(<VlogPage onNavigate={() => {}} />);
  await selectPet();
  await screen.findByText("公园散步");
  vi.spyOn(window, "confirm").mockReturnValue(true);
  fireEvent.click(screen.getByText("删除"));
  await screen.findByText("Vlog 已删除。");
  expect(mocks.remove).toHaveBeenCalledWith("v1");
});

it("shows load errors with retry", async () => {
  mocks.list.mockRejectedValue(new Error("后端不可用"));
  render(<VlogPage onNavigate={() => {}} />);
  await selectPet();
  await screen.findByText(/后端不可用/);
  mocks.list.mockResolvedValue([]);
  fireEvent.click(screen.getByText("重试"));
  await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2));
});
