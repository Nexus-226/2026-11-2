// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ChatPage from "../src/pages/ChatPage";

const mocks = vi.hoisted(() => ({
  send: vi.fn(),
  list: vi.fn(),
}));

vi.mock("../src/api/chat", () => ({
  chatClient: { send: mocks.send },
  usingDemoChat: false,
}));
vi.mock("../src/api/pets", () => ({
  petClient: { list: mocks.list },
  usingDemoData: false,
}));

const pet = {
  id: "b8f34f24-f5cf-4b5c-8d40-073541725a11",
  name: "豆豆",
  species: "dog",
  breed: null,
  birthday: null,
  notes: null,
  created_at: "2026-11-02T08:00:00Z",
  updated_at: "2026-11-02T08:00:00Z",
};
const response = {
  session_id: "d57700a2-a0a3-4bea-822c-9a8544def58e",
  message_id: "b0276f42-1264-4ac3-ac75-5d58269e8758",
  reply: "这是来自测试接口的回答。",
  tool_calls: [],
};

beforeEach(() => {
  mocks.send.mockReset();
  mocks.list.mockReset();
  mocks.list.mockResolvedValue([pet]);
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("聊天页面", () => {
  it("发送选中宠物和会话 ID，并显示两轮回复", async () => {
    const user = userEvent.setup();
    mocks.send.mockResolvedValue(response);
    render(<ChatPage active onNavigate={vi.fn()} />);

    expect(screen.getByText("今天想聊点什么？")).toBeTruthy();
    await screen.findByRole("option", { name: "豆豆" });
    await user.selectOptions(screen.getByLabelText("关联宠物"), pet.id);
    await user.type(screen.getByLabelText("输入你的问题"), "  豆豆怎么样？  ");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await screen.findByText(response.reply);
    expect(mocks.send.mock.calls[0][0]).toEqual({
      message: "豆豆怎么样？",
      pet_id: pet.id,
      session_id: null,
    });
    await user.type(screen.getByLabelText("输入你的问题"), "再说说");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(mocks.send).toHaveBeenCalledTimes(2));
    expect(mocks.send.mock.calls[1][0].session_id).toBe(response.session_id);
  });

  it("接口失败后展示真实错误，重试不重复插入用户消息", async () => {
    const user = userEvent.setup();
    mocks.send
      .mockRejectedValueOnce(new Error("模型暂不可用"))
      .mockResolvedValueOnce(response);
    render(<ChatPage active onNavigate={vi.fn()} />);
    await screen.findByRole("option", { name: "豆豆" });
    await user.type(screen.getByLabelText("输入你的问题"), "你好");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await screen.findByText("模型暂不可用");
    await user.click(screen.getByRole("button", { name: "重试" }));
    await screen.findByText(response.reply);
    expect(screen.getAllByText("你好")).toHaveLength(1);
    expect(mocks.send.mock.calls[1][0]).toEqual(mocks.send.mock.calls[0][0]);
  });

  it("停止等待会中止请求并提示服务端可能仍在处理", async () => {
    const user = userEvent.setup();
    mocks.send.mockImplementation(
      (_request: unknown, signal: AbortSignal) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    render(<ChatPage active onNavigate={vi.fn()} />);
    await screen.findByRole("option", { name: "豆豆" });
    await user.type(screen.getByLabelText("输入你的问题"), "你好");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(screen.getByRole("button", { name: "停止等待" }));

    await screen.findByText("已停止等待，服务端可能仍在处理中。");
    expect((mocks.send.mock.calls[0][1] as AbortSignal).aborted).toBe(true);
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
  });

  it("档案接口失败时仍可不关联宠物发送，且支持重试加载", async () => {
    const user = userEvent.setup();
    mocks.list
      .mockReset()
      .mockRejectedValueOnce(new Error("无法连接后端"))
      .mockResolvedValueOnce([pet]);
    mocks.send.mockResolvedValue(response);
    render(<ChatPage active onNavigate={vi.fn()} />);

    await screen.findByText(/宠物档案暂时无法加载/);
    await user.type(screen.getByLabelText("输入你的问题"), "你好");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await screen.findByText(response.reply);
    expect(mocks.send.mock.calls[0][0].pet_id).toBeNull();
    await user.click(screen.getByRole("button", { name: "重试加载" }));
    await screen.findByRole("option", { name: "豆豆" });
  });

  it("等待超时后释放加载状态并允许重试", async () => {
    vi.useFakeTimers();
    mocks.list.mockResolvedValue([]);
    mocks.send.mockImplementation(
      (_request: unknown, signal: AbortSignal) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    render(<ChatPage active onNavigate={vi.fn()} />);
    await act(async () => {});
    fireEvent.change(screen.getByLabelText("输入你的问题"), {
      target: { value: "你好" },
    });
    fireEvent.submit(screen.getByLabelText("输入你的问题").closest("form")!);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(screen.getByText(/等待超时/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    expect((mocks.send.mock.calls[0][1] as AbortSignal).aborted).toBe(true);
  });
});
