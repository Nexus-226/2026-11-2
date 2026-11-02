// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ChatPage from "../src/pages/ChatPage";

const list = vi.hoisted(() => vi.fn());

vi.mock("../src/api/chat", () => ({
  chatClient: { send: vi.fn() },
  usingDemoChat: false,
}));
vi.mock("../src/api/pets", () => ({
  petClient: { list },
  usingDemoData: true,
}));

afterEach(() => cleanup());

it("真实对话模式不会读取或传递本地演示宠物 ID", () => {
  render(<ChatPage active onNavigate={vi.fn()} />);
  expect(screen.getByText(/真实对话不能使用本地演示档案/)).toBeTruthy();
  expect(
    (screen.getByLabelText("关联宠物") as HTMLSelectElement).disabled,
  ).toBe(true);
  expect(list).not.toHaveBeenCalled();
});
