import type { RecordDraft } from "./records";

export interface ChatRequest {
  message: string;
  pet_id: string | null;
  session_id: string | null;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  reply: string;
  tool_calls: Array<{ name: string; status: "success" | "error" }>;
  draft: RecordDraft | null;
}

export interface ChatClient {
  send(request: ChatRequest, signal: AbortSignal): Promise<ChatResponse>;
}
