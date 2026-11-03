// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AddressResolver from "../src/components/nearby/AddressResolver";

const mocks = vi.hoisted(() => ({ resolveAddress: vi.fn() }));
vi.mock("../src/api/locations", () => ({
  resolveAddress: mocks.resolveAddress,
}));

beforeEach(() => {
  vi.resetAllMocks();
});
afterEach(cleanup);

it("resolves an address and lets the user pick a candidate", async () => {
  const match = {
    formatted_address: "北京市示例路 18 号",
    location: { lat: 39.9001, lng: 116.4001 },
    data_source: "amap",
  };
  mocks.resolveAddress.mockResolvedValue([match]);
  const onResolved = vi.fn();
  render(<AddressResolver onResolved={onResolved} />);
  fireEvent.change(screen.getByLabelText("手动输入地址"), {
    target: { value: "北京市示例路" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  const candidate = await screen.findByText("北京市示例路 18 号");
  fireEvent.click(candidate);
  expect(onResolved).toHaveBeenCalledWith(match);
});

it("validates a blank address before resolving", async () => {
  render(<AddressResolver onResolved={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("手动输入地址"), {
    target: { value: "   " },
  });
  fireEvent.click(screen.getByText("解析地址"));
  await screen.findByText("地址须为去除首尾空格后 1–200 个字符。");
  expect(mocks.resolveAddress).not.toHaveBeenCalled();
});

it("shows a resolution failure and keeps the input", async () => {
  mocks.resolveAddress.mockRejectedValueOnce(new Error("未找到匹配地址"));
  render(<AddressResolver onResolved={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("手动输入地址"), {
    target: { value: "不存在的地方" },
  });
  fireEvent.click(screen.getByText("解析地址"));
  await screen.findByText("未找到匹配地址");
  expect(
    (screen.getByLabelText("手动输入地址") as HTMLInputElement).value,
  ).toBe("不存在的地方");
});
