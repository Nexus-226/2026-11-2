import type { ChatClient, ChatRequest, ChatResponse } from "../types/chat";

function isChatResponse(value: unknown): value is ChatResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return (
    typeof response.session_id === "string" &&
    response.session_id.length > 0 &&
    typeof response.message_id === "string" &&
    response.message_id.length > 0 &&
    typeof response.reply === "string" &&
    response.reply.trim().length > 0 &&
    Array.isArray(response.tool_calls) &&
    response.tool_calls.every(
      (item: unknown) =>
        !!item &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).name === "string" &&
        ((item as Record<string, unknown>).status === "success" ||
          (item as Record<string, unknown>).status === "error"),
    )
  );
}

async function sendToApi(
  request: ChatRequest,
  signal: AbortSignal,
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error("无法连接后端，请检查服务是否启动后重试。");
  }

  if (!response.ok) {
    let message = `请求失败（${response.status}），请稍后重试。`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "error" in body) {
        const details = (body as { error?: { message?: unknown } }).error;
        if (typeof details?.message === "string" && details.message.trim()) {
          message = details.message;
        }
      }
    } catch {
      // Keep the status-based message when the response is not the agreed JSON format.
    }
    throw new Error(message);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("后端返回的数据格式不正确，请联系开发人员。");
  }
  if (!isChatResponse(body)) {
    throw new Error("后端返回的对话数据不符合接口约定，请联系开发人员。");
  }
  return body;
}

const demoClient: ChatClient = {
  send(request, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException("请求已中止", "AbortError"));
        return;
      }
      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException("请求已中止", "AbortError"));
      };
      const timer = window.setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        resolve({
          session_id:
            request.session_id ?? "00000000-0000-4000-8000-000000000001",
          message_id: "00000000-0000-4000-8000-000000000002",
          reply:
            "这是演示回复，用来检查聊天界面。当前没有连接真实模型，请勿将此内容当作宠物护理建议。",
          tool_calls: [],
        });
      }, 500);
      signal.addEventListener("abort", onAbort, { once: true });
    });
  },
};

const apiClient: ChatClient = { send: sendToApi };

// Choose explicitly; API failures never switch silently to a simulated answer.
export const usingDemoChat = import.meta.env.VITE_CHAT_DATA_SOURCE !== "api";
export const chatClient = usingDemoChat ? demoClient : apiClient;
