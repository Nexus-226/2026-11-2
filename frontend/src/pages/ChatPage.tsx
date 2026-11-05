import { useAppScope, useAppGuard } from "../app/AppScope";
import PetSwitcher from "../components/navigation/PetSwitcher";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { chatClient, usingDemoChat } from "../api/chat";
import { petClient, usingDemoData } from "../api/pets";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import AssistantMessage from "../components/chat/AssistantMessage";
import type { ChatRequest } from "../types/chat";
import type { Pet } from "../types/pet";

interface ChatPageProps {
  active: boolean;
  onNavigate: (page: AppPage) => void;
}

interface Message {
  key: number;
  role: "user" | "assistant";
  text: string;
}

const REQUEST_TIMEOUT_MS = 30_000;

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败，请稍后重试。";
}

export default function ChatPage({ active, onNavigate }: ChatPageProps) {
  const shared = useAppScope();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [localSelectedPetId, setSelectedPetId] = useState("");
  const selectedPetIdRef = useRef("");
  const [pets, setPets] = useState<Pet[]>([]);
  const [petsLoading, setPetsLoading] = useState(false);
  const [petsError, setPetsError] = useState("");
  const [petReloadKey, setPetReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failedRequest, setFailedRequest] = useState<ChatRequest | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);
  const nextMessageKey = useRef(0);
  const endRef = useRef<HTMLLIElement | null>(null);
  const canSelectPets = usingDemoChat || !usingDemoData;
  const selectedPetId = shared
    ? canSelectPets
      ? shared.petId || ""
      : ""
    : localSelectedPetId;
  useAppGuard("chat", {
    busy,
    warning: (kind) =>
      kind === "pet" && messages.length
        ? "切换宠物会开始新对话，当前页面聊天记录将清空。"
        : active && draft
          ? "问题尚未发送，继续将丢弃输入。"
          : null,
    onPetChange: () => resetSession("关联宠物已变更，已开始新对话。"),
    onLeave: () => {
      if (active) setDraft("");
    },
  });

  useEffect(() => {
    if (!active) return;
    if (shared) {
      setPets(canSelectPets ? shared.pets : []);
      setPetsLoading(shared.loading);
      setPetsError(shared.error);
      return;
    }
    if (!canSelectPets) {
      clearInvalidPet();
      setPets([]);
      setPetsLoading(false);
      setPetsError("");
      return;
    }
    let current = true;
    setPetsLoading(true);
    setPetsError("");
    petClient
      .list()
      .then((items) => {
        if (!current) return;
        setPets(items);
        if (!items.some((item) => item.id === selectedPetIdRef.current)) {
          clearInvalidPet();
        }
      })
      .catch((error: unknown) => {
        if (!current) return;
        setPets([]);
        clearInvalidPet();
        setPetsError(messageFromError(error));
      })
      .finally(() => {
        if (current) setPetsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [
    active,
    canSelectPets,
    petReloadKey,
    shared?.pets,
    shared?.loading,
    shared?.error,
  ]);

  useEffect(() => {
    if (active && messages.length > 0) {
      endRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [active, messages, busy]);

  useEffect(
    () => () => {
      requestRef.current?.abort("unmount");
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  async function runRequest(request: ChatRequest, addUserMessage: boolean) {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setNotice("");
    setFailedRequest(null);
    if (addUserMessage) {
      setMessages((current) => [
        ...current,
        { key: ++nextMessageKey.current, role: "user", text: request.message },
      ]);
      setDraft("");
    }

    timerRef.current = window.setTimeout(
      () => controller.abort("timeout"),
      REQUEST_TIMEOUT_MS,
    );
    try {
      const response = await chatClient.send(request, controller.signal);
      if (controller.signal.aborted) return;
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        {
          key: ++nextMessageKey.current,
          role: "assistant",
          text: response.reply,
        },
      ]);
    } catch (error) {
      if (
        requestRef.current !== controller ||
        controller.signal.reason === "unmount"
      )
        return;
      if (controller.signal.aborted) {
        setNotice(
          controller.signal.reason === "timeout"
            ? "等待超时，服务端可能仍在处理；重试可能产生重复请求。"
            : "已停止等待，服务端可能仍在处理中。",
        );
      } else {
        setNotice(messageFromError(error));
      }
      setFailedRequest(request);
    } finally {
      if (requestRef.current === controller) {
        if (timerRef.current !== null) window.clearTimeout(timerRef.current);
        timerRef.current = null;
        requestRef.current = null;
        if (controller.signal.reason !== "unmount") setBusy(false);
      }
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) {
      setNotice("请输入问题后再发送。");
      return;
    }
    if (message.length > 4000) {
      setNotice("问题不能超过 4000 个字符。");
      return;
    }
    void runRequest(
      { message, pet_id: selectedPetId || null, session_id: sessionId },
      true,
    );
  }

  function resetSession(notice = "") {
    requestRef.current?.abort("session-reset");
    requestRef.current = null;
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    setBusy(false);
    setMessages([]);
    setDraft("");
    setSessionId(null);
    setFailedRequest(null);
    setNotice(notice);
  }

  function clearInvalidPet() {
    if (!selectedPetIdRef.current) return;
    selectedPetIdRef.current = "";
    setSelectedPetId("");
    resetSession("关联宠物已失效或暂时无法验证，已清空关联并开始新对话。");
  }

  function startNewSession() {
    if (requestRef.current) return;
    if (
      messages.length > 0 &&
      !window.confirm("确定开始新对话吗？当前页面的聊天记录将清空。")
    ) {
      return;
    }
    resetSession();
  }

  function changePet(nextPetId: string) {
    if (requestRef.current || nextPetId === selectedPetId) return;
    if (
      messages.length > 0 &&
      !window.confirm(
        "切换或清空关联宠物将开始新对话，当前页面的聊天记录将清空。是否继续？",
      )
    )
      return;
    selectedPetIdRef.current = nextPetId;
    setSelectedPetId(nextPetId);
    resetSession("关联宠物已变更，已开始新对话。");
  }

  return (
    <div className="app-shell">
      <AppHeader active="chat" onNavigate={onNavigate} />
      <main className="page chat-page">
        <div className="chat-intro">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true">✳</span> &nbsp; PET COMPANION
            </p>
            <h1>
              关于它，聊聊吧<span className="heading-dot">.</span>
            </h1>
            <p className="subtitle">从一个小问题开始，让陪伴更从容。</p>
          </div>
          <span className="heading-illustration" aria-hidden="true">
            ♡<span>✦</span>
          </span>
        </div>

        <PetSwitcher
          label="本次对话关联"
          disabled={busy || !canSelectPets}
          unlinked={!canSelectPets}
        />
        <div
          className={`mode-banner ${usingDemoChat ? "demo" : "connected"}`}
          role="status"
        >
          <span className="mode-dot" aria-hidden="true" />
          <div>
            <strong>
              {usingDemoChat ? "当前为对话演示模式" : "当前为对话接口模式"}
            </strong>
            <span>
              {usingDemoChat
                ? "回复为固定示例，未连接真实模型；聊天记录仅保留在当前页面。"
                : "通过后端发送消息；聊天记录仅在当前页面展示。"}
            </span>
          </div>
        </div>

        <section className="chat-card" aria-label="宠物助手对话">
          <div className="chat-toolbar">
            <div className="chat-persona">
              <span className="assistant-avatar" aria-hidden="true">
                ✦
              </span>
              <div>
                <strong>宠物助手</strong>
                <small>一起来关心它的每一天</small>
              </div>
            </div>
            <button
              type="button"
              className="new-chat"
              onClick={startNewSession}
              disabled={busy}
            >
              <span aria-hidden="true">＋</span> 新对话
            </button>
          </div>

          {!shared && (
            <>
              <div className="context-row">
                <label htmlFor="chat-pet">关联宠物</label>
                <select
                  id="chat-pet"
                  value={selectedPetId}
                  disabled={busy || petsLoading || !canSelectPets}
                  onChange={(event) => changePet(event.target.value)}
                >
                  <option value="">暂不关联宠物</option>
                  {pets.map((pet) => (
                    <option key={pet.id} value={pet.id}>
                      {pet.name}
                    </option>
                  ))}
                </select>
                <span className="context-hint">
                  {petsLoading
                    ? "正在加载档案…"
                    : pets.length
                      ? "可选，发送时带上档案"
                      : "可以不关联，直接提问"}
                </span>
              </div>
            </>
          )}
          {!canSelectPets && (
            <div className="context-message" role="status">
              真实对话不能使用本地演示档案。可以先不关联宠物，或切换到后端档案。
            </div>
          )}
          {petsError && (
            <div className="context-message context-error" role="alert">
              <span>
                宠物档案暂时无法加载：{petsError} 你仍可不关联宠物继续对话。
              </span>
              <button
                type="button"
                onClick={() =>
                  shared
                    ? shared.reloadPets()
                    : setPetReloadKey((value) => value + 1)
                }
              >
                重试加载
              </button>
            </div>
          )}

          <div
            className="chat-body"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.length === 0 ? (
              <div className="chat-empty">
                <span className="chat-empty-icon" aria-hidden="true">
                  ✽
                </span>
                <h2>今天想聊点什么？</h2>
                <p>可以问问日常照护、陪伴，或关于它的小疑问。</p>
                <div className="suggestions">
                  <button
                    type="button"
                    onClick={() => setDraft("日常护理需要注意哪些事情？")}
                  >
                    日常护理需要注意什么？ <span aria-hidden="true">↗</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDraft("新宠物到家需要准备什么？")}
                  >
                    新宠物到家要准备什么？ <span aria-hidden="true">↗</span>
                  </button>
                </div>
              </div>
            ) : (
              <ol className="message-list" aria-label="聊天记录">
                {messages.map((message) => (
                  <li
                    key={message.key}
                    className={`message-row ${message.role}`}
                  >
                    {message.role === "assistant" && (
                      <span className="message-avatar" aria-hidden="true">
                        ✦
                      </span>
                    )}
                    <div className="message-content">
                      <span className="message-label">
                        {message.role === "user"
                          ? "你"
                          : usingDemoChat
                            ? "演示回复"
                            : "宠物助手"}
                      </span>
                      <div className="message-bubble">
                        {message.role === "assistant" ? (
                          <AssistantMessage text={message.text} />
                        ) : (
                          message.text
                        )}
                      </div>
                    </div>
                  </li>
                ))}
                {busy && (
                  <li className="message-row assistant">
                    <span className="message-avatar" aria-hidden="true">
                      ✦
                    </span>
                    <div className="message-content">
                      <span className="message-label">宠物助手</span>
                      <div className="message-bubble typing" role="status">
                        <span className="spinner" aria-hidden="true" />{" "}
                        正在等待回复…
                      </div>
                    </div>
                  </li>
                )}
                <li ref={endRef} aria-hidden="true" />
              </ol>
            )}
          </div>

          {notice && (
            <div className="chat-notice" role="alert">
              <span>{notice}</span>
              {failedRequest && !busy && (
                <button
                  type="button"
                  onClick={() => void runRequest(failedRequest, false)}
                >
                  重试
                </button>
              )}
            </div>
          )}

          <form className="composer-wrap" onSubmit={handleSubmit}>
            <label htmlFor="chat-message" className="visually-hidden">
              输入你的问题
            </label>
            <div className="composer">
              <textarea
                id="chat-message"
                rows={2}
                maxLength={4000}
                placeholder="输入你想问的问题…"
                value={draft}
                disabled={busy}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              {busy ? (
                <button
                  className="button stop-button"
                  type="button"
                  onClick={() => requestRef.current?.abort("cancelled")}
                >
                  停止等待
                </button>
              ) : (
                <button
                  className="button send-button"
                  type="submit"
                  disabled={!draft.trim()}
                >
                  发送 <span aria-hidden="true">↗</span>
                </button>
              )}
            </div>
            <div className="composer-footer">
              <span>Enter 发送 · Shift + Enter 换行</span>
              <span>{draft.length} / 4000</span>
            </div>
          </form>
          <p className="chat-disclaimer">
            宠物健康信息仅供参考；如遇紧急情况，请及时联系专业兽医。
          </p>
        </section>
        <footer className="page-footer">
          <span>MADE FOR THE LITTLE ONES ♡</span>
          <span>宠爱，从了解开始。</span>
        </footer>
      </main>
    </div>
  );
}
