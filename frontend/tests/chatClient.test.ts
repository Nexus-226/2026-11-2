// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const request = { message: "你好", pet_id: null, session_id: null };
const response = {
  session_id: "d57700a2-a0a3-4bea-822c-9a8544def58e",
  message_id: "b0276f42-1264-4ac3-ac75-5d58269e8758",
  reply: "来自后端的回复",
  tool_calls: [],
};

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("VITE_CHAT_DATA_SOURCE", "api");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("对话 API Client", () => {
  it("按约定发送 JSON 和 AbortSignal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { chatClient, usingDemoChat } = await import("../src/api/chat");
    const controller = new AbortController();
    const result = await chatClient.send(request, controller.signal);

    expect(usingDemoChat).toBe(false);
    expect(result).toEqual(response);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
        signal: controller.signal,
      }),
    );
  });

  it("接口错误直接返回，不静默生成演示回复", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { message: "服务暂不可用" } }), {
          status: 503,
        }),
      ),
    );
    const { chatClient } = await import("../src/api/chat");
    await expect(
      chatClient.send(request, new AbortController().signal),
    ).rejects.toThrow("服务暂不可用");
  });

  it("拒绝缺失必要字段的后端响应", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ reply: "不完整" }), { status: 200 }),
        ),
    );
    const { chatClient } = await import("../src/api/chat");
    await expect(
      chatClient.send(request, new AbortController().signal),
    ).rejects.toThrow("不符合接口约定");
  });

  it("接受带洗澡记录草稿的响应", async () => {
    const draft = {
      record_type: "bath",
      occurred_on: "2026-01-01",
      pet_id: "b8f34f24-f5cf-4b5c-8d40-073541725a11",
      name: null,
      notes: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...response, draft }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { chatClient } = await import("../src/api/chat");
    const result = await chatClient.send(request, new AbortController().signal);
    expect(result.draft).toEqual(draft);
  });

  it("拒绝草稿字段不合法的响应", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ ...response, draft: { record_type: "vaccine" } }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    const { chatClient } = await import("../src/api/chat");
    await expect(
      chatClient.send(request, new AbortController().signal),
    ).rejects.toThrow("不符合接口约定");
  });
});
