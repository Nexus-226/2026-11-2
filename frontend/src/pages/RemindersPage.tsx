import { useEffect, useState, type FormEvent } from "react";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import { petClient, usingDemoData } from "../api/pets";
import { recordClient, usingDemoRecords } from "../api/records";
import { reminderClient, usingDemoReminders } from "../api/reminders";
import { type PetReminder, type ReminderStatus } from "../types/reminders";
import {
  shanghaiToday,
  type PetRecord,
  type RecordType,
} from "../types/records";
import type { Pet } from "../types/pet";
import "../styles/reminders.css";

const recordTypeLabels: Record<RecordType, string> = {
  vaccine: "疫苗",
  deworming: "驱虫",
  bath: "洗澡",
  weight: "体重",
};

const recordLabel = (r: PetRecord) =>
  `${recordTypeLabels[r.record_type]} · ${r.occurred_on}${r.name ? ` · ${r.name}` : ""}`;

const msg = (e: unknown) =>
  e instanceof Error ? e.message : "操作失败，请重试。";

export default function RemindersPage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const [pets, setPets] = useState<Pet[]>([]),
    [scope, setScope] = useState("unlinked"),
    [items, setItems] = useState<PetReminder[]>([]),
    [records, setRecords] = useState<PetRecord[]>([]);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [petError, setPetError] = useState(""),
    [recordsError, setRecordsError] = useState(""),
    [formError, setFormError] = useState(""),
    [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<PetReminder | null>(null),
    [title, setTitle] = useState(""),
    [dueOn, setDueOn] = useState(shanghaiToday),
    [sourceRecordId, setSourceRecordId] = useState("");
  const mismatch = !usingDemoReminders && usingDemoData;
  const recordsMismatch = !usingDemoReminders && usingDemoRecords;

  useEffect(() => {
    let live = true;
    petClient
      .list()
      .then((p) => {
        if (live) {
          setPets(p);
          setPetError("");
        }
      })
      .catch((e) => {
        if (live) setPetError(msg(e));
      });
    return () => {
      live = false;
    };
  }, [reload]);

  useEffect(() => {
    let live = true;
    setItems([]);
    setError("");
    setLoading(true);
    reminderClient
      .list(scope === "unlinked" ? { unlinked: true } : { pet_id: scope })
      .then((r) => {
        if (live) setItems(r);
      })
      .catch((e) => {
        if (live) setError(msg(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [scope, reload]);

  useEffect(() => {
    let live = true;
    setRecords([]);
    setRecordsError("");
    recordClient
      .list(scope === "unlinked" ? { unlinked: true } : { pet_id: scope })
      .then((r) => {
        if (live) setRecords(r);
      })
      .catch((e) => {
        if (live) setRecordsError(msg(e));
      });
    return () => {
      live = false;
    };
  }, [scope, reload]);

  function reset() {
    setEditing(null);
    setTitle("");
    setDueOn(shanghaiToday());
    setSourceRecordId("");
    setFormError("");
  }

  function startEdit(item: PetReminder) {
    setEditing(item);
    setTitle(item.title);
    setDueOn(item.due_on);
    setSourceRecordId(item.source_record_id ?? "");
    setFormError("");
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    setNotice("");
    const trimmed = title.trim();
    if (!trimmed || trimmed.length > 120) {
      setFormError("标题须为 1–120 个字符。");
      return;
    }
    if (!dueOn) {
      setFormError("请填写到期日期。");
      return;
    }
    setBusy(true);
    const input = {
      pet_id: scope === "unlinked" ? null : scope,
      title: trimmed,
      due_on: dueOn,
      source_record_id: sourceRecordId || null,
    };
    try {
      if (editing) await reminderClient.update(editing.id, input);
      else await reminderClient.create(input);
      reset();
      setNotice("提醒已保存。");
      setReload((v) => v + 1);
    } catch (e) {
      setFormError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(item: PetReminder, status: ReminderStatus) {
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      await reminderClient.update(item.id, { status });
      if (editing?.id === item.id) reset();
      setNotice(status === "completed" ? "已标记完成。" : "已取消提醒。");
      setReload((v) => v + 1);
    } catch (e) {
      setFormError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: PetReminder) {
    if (!window.confirm("删除这条提醒？")) return;
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      await reminderClient.remove(item.id);
      if (editing?.id === item.id) reset();
      setNotice("提醒已删除。");
      setReload((v) => v + 1);
    } catch (e) {
      setFormError(msg(e));
    } finally {
      setBusy(false);
    }
  }

  const pending = items.filter((i) => i.status === "pending");
  const groups = [
    { label: "逾期", items: pending.filter((i) => i.due_group === "overdue") },
    { label: "今天", items: pending.filter((i) => i.due_group === "today") },
    {
      label: "即将",
      items: pending.filter((i) => i.due_group === "upcoming"),
    },
    { label: "更晚", items: pending.filter((i) => i.due_group === "later") },
    {
      label: "已完成",
      items: items.filter((i) => i.status === "completed"),
    },
    {
      label: "已取消",
      items: items.filter((i) => i.status === "cancelled"),
    },
  ].filter((g) => g.items.length > 0);

  return (
    <>
      <AppHeader
        active="reminders"
        onNavigate={onNavigate}
        navigationDisabled={busy}
      />
      <main className="reminders-page">
        <header>
          <p className="eyebrow">
            <span aria-hidden="true">✳</span> &nbsp; REMINDERS
          </p>
          <h1>待办提醒</h1>
          <p className="subtitle">计划要做的护理事项，到期前提醒你。</p>
          <p className="reminders-source">
            {usingDemoReminders
              ? "本地演示数据 · 仅保存在当前浏览器，不同步后端"
              : "后端 API 数据 · 以服务端保存结果为准"}
          </p>
        </header>
        {mismatch && (
          <p role="alert">
            API 提醒需要设置 VITE_PET_DATA_SOURCE=api
            并重启。当前仅可操作未关联提醒。
          </p>
        )}
        {petError && (
          <p role="alert">
            宠物列表加载失败：{petError}
            <button onClick={() => setReload((v) => v + 1)}>重试</button>
          </p>
        )}
        <section className="reminders-filters" aria-label="提醒范围">
          <label>
            宠物范围
            <select
              disabled={busy}
              value={scope}
              onChange={(e) => {
                setScope(e.target.value);
                reset();
                setNotice("");
              }}
            >
              <option value="unlinked">未关联宠物</option>
              {!mismatch &&
                pets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </label>
          <button disabled={busy} onClick={() => setReload((v) => v + 1)}>
            刷新提醒
          </button>
        </section>
        <div className="reminders-layout">
          <section className="reminders-panel">
            <h2>{editing ? "编辑提醒" : "添加提醒"}</h2>
            <p>
              当前：
              {scope === "unlinked"
                ? "未关联宠物"
                : (pets.find((p) => p.id === scope)?.name ?? "所选宠物")}
            </p>
            <form onSubmit={save}>
              <fieldset disabled={busy}>
                <label>
                  标题
                  <input
                    required
                    maxLength={120}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                <label>
                  到期日期（上海时区）
                  <input
                    required
                    type="date"
                    value={dueOn}
                    onChange={(e) => setDueOn(e.target.value)}
                  />
                </label>
                {recordsMismatch ? (
                  <p>
                    来源记录需要设置 VITE_RECORD_DATA_SOURCE=api
                    并重启后才可用；当前无法关联来源记录。
                  </p>
                ) : (
                  <label>
                    来源记录（可选）
                    <select
                      value={sourceRecordId}
                      onChange={(e) => setSourceRecordId(e.target.value)}
                    >
                      <option value="">无来源</option>
                      {records.map((r) => (
                        <option key={r.id} value={r.id}>
                          {recordLabel(r)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {recordsError && <p role="alert">{recordsError}</p>}
                {formError && <p role="alert">{formError}</p>}
                <button type="submit">{busy ? "处理中…" : "保存提醒"}</button>
                {editing && (
                  <button type="button" onClick={reset}>
                    取消编辑
                  </button>
                )}
              </fieldset>
            </form>
            <p role="status">{notice}</p>
          </section>
          <section className="reminders-panel" aria-label="待办卡片">
            <h2>待办</h2>
            {loading ? (
              <p role="status">正在加载提醒…</p>
            ) : error ? (
              <p role="alert">
                {error}
                <button onClick={() => setReload((v) => v + 1)}>重试</button>
              </p>
            ) : groups.length === 0 ? (
              <p>当前范围暂无提醒。</p>
            ) : (
              groups.map((group) => (
                <div key={group.label} className="reminder-group">
                  <h3>{group.label}</h3>
                  <ul>
                    {group.items.map((item) => (
                      <li key={item.id}>
                        <time>{item.due_on}</time>
                        <p className="reminder-title">{item.title}</p>
                        {item.source_record_id && (
                          <p className="reminder-source">
                            来源：
                            {records.find((r) => r.id === item.source_record_id)
                              ? recordLabel(
                                  records.find(
                                    (r) => r.id === item.source_record_id,
                                  )!,
                                )
                              : "记录已删除"}
                          </p>
                        )}
                        <div className="reminder-actions">
                          {item.status === "pending" && (
                            <>
                              <button
                                disabled={busy}
                                onClick={() => setStatus(item, "completed")}
                              >
                                完成
                              </button>
                              <button
                                disabled={busy}
                                onClick={() => setStatus(item, "cancelled")}
                              >
                                取消
                              </button>
                            </>
                          )}
                          <button
                            disabled={busy}
                            onClick={() => startEdit(item)}
                          >
                            编辑
                          </button>
                          <button disabled={busy} onClick={() => remove(item)}>
                            删除
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </section>
        </div>
      </main>
    </>
  );
}
