import AppIcon from "../components/navigation/AppIcon";
import { useAppScope, useAppGuard } from "../app/AppScope";
import PetSwitcher from "../components/navigation/PetSwitcher";
import { useEffect, useRef, useState, type FormEvent } from "react";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import { petClient, usingDemoData } from "../api/pets";
import { recordClient, usingDemoRecords } from "../api/records";
import {
  shanghaiToday,
  type PetRecord,
  type RecordType,
} from "../types/records";
import type { Pet } from "../types/pet";
import "../styles/records.css";
import WeightTrend from "../components/common/WeightTrend";
const labels: Record<RecordType, string> = {
  vaccine: "疫苗",
  deworming: "驱虫",
  bath: "洗澡",
  weight: "体重",
};
const msg = (e: unknown) =>
  e instanceof Error ? e.message : "操作失败，请重试。";
export default function RecordsPage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const shared = useAppScope();
  const [pets, setPets] = useState<Pet[]>([]),
    [localScope, setScope] = useState("unlinked"),
    [items, setItems] = useState<PetRecord[]>([]);
  const [kind, setKind] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [petError, setPetError] = useState(""),
    [formError, setFormError] = useState(""),
    [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<PetRecord | null>(null),
    [type, setType] = useState<RecordType>("deworming"),
    [date, setDate] = useState(shanghaiToday),
    [name, setName] = useState(""),
    [weight, setWeight] = useState(""),
    [notes, setNotes] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const formRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (formOpen)
      formRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" });
  }, [formOpen]);
  const [trendRange, setTrendRange] = useState("90");
  const mismatch = !usingDemoRecords && usingDemoData;
  const scope = shared
    ? mismatch
      ? "unlinked"
      : shared.petId || "unlinked"
    : localScope;
  useEffect(() => {
    if (shared) {
      setPets(shared.pets);
      setPetError(shared.error);
      return;
    }
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
  }, [reload, shared?.pets, shared?.error]);
  useEffect(() => {
    let live = true;
    setItems([]);
    setError("");
    setLoading(true);
    if (from && to && from > to) {
      setError("开始日期不能晚于结束日期。");
      setLoading(false);
      return;
    }
    recordClient
      .list({
        ...(scope === "unlinked" ? { unlinked: true } : { pet_id: scope }),
        ...(kind ? { record_type: kind as RecordType } : {}),
        ...(from ? { from_date: from } : {}),
        ...(to ? { to_date: to } : {}),
      })
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
  }, [scope, kind, from, to, reload]);
  function reset() {
    setFormOpen(false);
    setEditing(null);
    setType("deworming");
    setDate(shanghaiToday());
    setName("");
    setWeight("");
    setNotes("");
    setFormError("");
  }
  const currentItems = items.filter(
    (item) => item.pet_id === (scope === "unlinked" ? null : scope),
  );
  const dirty = editing
    ? type !== editing.record_type ||
      date !== editing.occurred_on ||
      name !== (editing.name || "") ||
      weight !== (editing.weight_kg?.toString() || "") ||
      notes !== (editing.notes || "")
    : type !== "deworming" ||
      date !== shanghaiToday() ||
      !!name ||
      !!weight ||
      !!notes;
  useAppGuard("records", {
    busy,
    warning: () => (dirty ? "记录修改尚未保存，继续将丢弃草稿。" : null),
    onPetChange: reset,
    onLeave: reset,
  });
  async function save(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    setNotice("");
    if (!date || date > shanghaiToday()) {
      setFormError("记录日期不能晚于上海时区今天。");
      return;
    }
    if (
      type === "weight" &&
      (!/^\d+(\.\d{1,2})?$/.test(weight) ||
        Number(weight) <= 0 ||
        Number(weight) > 500)
    ) {
      setFormError("体重须大于 0 且不超过 500 kg，最多两位小数。");
      return;
    }
    setBusy(true);
    const input = {
      pet_id: scope === "unlinked" ? null : scope,
      record_type: type,
      occurred_on: date,
      name: name.trim() || null,
      weight_kg: type === "weight" ? Number(weight) : null,
      notes: notes.trim() || null,
    };
    try {
      if (editing) await recordClient.update(editing.id, input);
      else await recordClient.create(input);
      reset();
      setNotice("记录已保存。");
      setReload((v) => v + 1);
    } catch (e) {
      setFormError(msg(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove(item: PetRecord) {
    if (!window.confirm("删除这条记录？关联提醒会保留。")) return;
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      await recordClient.remove(item.id);
      if (editing?.id === item.id) reset();
      setNotice("记录已删除。");
      setReload((v) => v + 1);
    } catch (e) {
      setFormError(msg(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <AppHeader
        active="records"
        onNavigate={onNavigate}
        navigationDisabled={busy}
      />
      <main className="records-page">
        <header className="page-heading">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true">✳</span> &nbsp; CARE JOURNAL
            </p>
            <h1>
              日常记录<span className="heading-dot">.</span>
            </h1>
            <p className="subtitle">保存已经发生的护理和体重变化。</p>
          </div>
          <span className="heading-illustration" aria-hidden="true">
            ♡<span>✦</span>
          </span>
        </header>
        <PetSwitcher
          label="当前查看范围"
          disabled={busy || mismatch}
          unlinked={mismatch}
        />
        <div
          className={`mode-banner ${usingDemoRecords ? "demo" : "connected"}`}
          role="status"
        >
          <span className="mode-dot" aria-hidden="true" />
          <div>
            <strong>
              {usingDemoRecords ? "本地演示数据" : "后端 API 数据"}
            </strong>
            <span>
              {usingDemoRecords
                ? "仅保存在当前浏览器，不同步后端"
                : "以服务端保存结果为准"}
            </span>
          </div>
        </div>
        {mismatch && (
          <p role="alert">
            API 记录需要设置 VITE_PET_DATA_SOURCE=api
            并重启。当前仅可操作未关联记录。
          </p>
        )}
        {petError && (
          <p role="alert">
            宠物列表加载失败：{petError}
            <button onClick={() => setReload((v) => v + 1)}>重试</button>
          </p>
        )}
        {shared && (
          <section className="care-category-section" aria-label="记录分类">
            <div className="care-section-heading">
              <div>
                <span className="section-kicker">CARE JOURNAL</span>
                <h2>每一份照顾，都有记录</h2>
              </div>
              <button
                className="button primary"
                disabled={busy}
                onClick={() => {
                  if (!dirty || window.confirm("放弃当前草稿并添加新记录？")) {
                    reset();
                    setType(kind ? (kind as RecordType) : "deworming");
                    setFormOpen(true);
                  }
                }}
              >
                ＋ 添加记录
              </button>
            </div>
            <div className="record-kind-cards">
              {Object.entries(labels).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={kind === id}
                  disabled={busy}
                  onClick={() => setKind(kind === id ? "" : id)}
                >
                  <AppIcon
                    name={id as "vaccine" | "deworming" | "bath" | "weight"}
                  />
                  <strong>{label}</strong>
                  <small>查看记录</small>
                </button>
              ))}
            </div>
            <div className="category-hint">
              <span>点击类别筛选记录</span>
              <button disabled={busy || !kind} onClick={() => setKind("")}>
                查看全部
              </button>
            </div>
          </section>
        )}
        <details
          className={shared ? "care-date-filter" : "legacy-filters"}
          open={shared ? undefined : true}
        >
          <summary>日期筛选与刷新</summary>
          <section className="records-filters" aria-label="记录筛选">
            {!shared && (
              <>
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
              </>
            )}
            <label className="record-type-select">
              筛选类型
              <select
                disabled={busy}
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="">全部类型</option>
                {Object.entries(labels).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              开始日期
              <input
                disabled={busy}
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
            <label>
              结束日期
              <input
                disabled={busy}
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
            <button disabled={busy} onClick={() => setReload((v) => v + 1)}>
              刷新记录
            </button>
          </section>
        </details>
        {shared && notice && (
          <div className="notice success" role="status">
            {notice}
          </div>
        )}
        {shared && formError && (
          <div className="notice error" role="alert">
            {formError}
          </div>
        )}
        <div className="records-layout">
          <section
            ref={formRef}
            className={`form-panel ${shared ? "care-form" : ""} ${formOpen ? "is-open" : ""}`}
            id="record-weight"
          >
            <div className="form-heading">
              <div>
                <span className="section-kicker">ADD RECORD</span>
                <h2>{editing ? "编辑记录" : "添加记录"}</h2>
                <p>
                  当前：
                  {scope === "unlinked"
                    ? "未关联宠物"
                    : (pets.find((p) => p.id === scope)?.name ?? "所选宠物")}
                </p>
              </div>
              <span className="form-flower" aria-hidden="true">
                ✽
              </span>
            </div>
            {!shared && notice && (
              <div className="notice success" role="status">
                {notice}
              </div>
            )}
            {!shared && formError && (
              <div className="notice error" role="alert">
                {formError}
              </div>
            )}
            {shared && (
              <button
                className="close-care-form"
                disabled={busy}
                onClick={() => {
                  if (!dirty || window.confirm("放弃未保存的记录内容？"))
                    reset();
                }}
                aria-label="关闭记录表单"
              >
                ×
              </button>
            )}
            <form onSubmit={save}>
              <fieldset className="field-grid" disabled={busy}>
                <label className="field">
                  <span>护理类型</span>
                  <select
                    value={type}
                    onChange={(e) => {
                      setType(e.target.value as RecordType);
                      setWeight("");
                    }}
                  >
                    {Object.entries(labels).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>发生日期（上海时区）</span>
                  <input
                    required
                    type="date"
                    max={shanghaiToday()}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </label>
                <label className="field">
                  <span>项目或产品名称</span>
                  <input
                    maxLength={100}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                {type === "weight" && (
                  <label className="field">
                    <span>体重（kg）</span>
                    <input
                      required
                      type="number"
                      min="0.01"
                      max="500"
                      step="0.01"
                      value={weight}
                      onChange={(e) => setWeight(e.target.value)}
                    />
                  </label>
                )}
                <label className="field field-wide">
                  <span>备注</span>
                  <textarea
                    maxLength={2000}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </label>
              </fieldset>
              <div className="form-actions">
                <button type="submit" className="button primary">
                  {busy ? "处理中…" : "保存记录"}
                </button>
                {editing && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={reset}
                  >
                    取消编辑
                  </button>
                )}
              </div>
            </form>
          </section>
          <section className="records-panel" aria-label="记录时间线">
            <div className="panel-title">
              <div>
                <span className="section-kicker">TIMELINE</span>
                <h2>记录时间线</h2>
              </div>
            </div>
            {loading ? (
              <p role="status">正在加载记录…</p>
            ) : error ? (
              <p role="alert">
                {error}
                <button onClick={() => setReload((v) => v + 1)}>重试</button>
              </p>
            ) : currentItems.length === 0 ? (
              <p>当前筛选下暂无记录。</p>
            ) : (
              <ol>
                {currentItems.map((item) => (
                  <li key={item.id}>
                    <time>{item.occurred_on}</time>
                    <h3>
                      {labels[item.record_type]}
                      {item.record_type === "weight"
                        ? ` · ${item.weight_kg} kg`
                        : ""}
                    </h3>
                    {item.name && <p>{item.name}</p>}
                    {item.notes && <p className="record-notes">{item.notes}</p>}
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (
                          dirty &&
                          !window.confirm("放弃当前草稿并编辑这条记录？")
                        )
                          return;
                        setFormOpen(true);
                        setEditing(item);
                        setType(item.record_type);
                        setDate(item.occurred_on);
                        setName(item.name ?? "");
                        setWeight(item.weight_kg?.toString() ?? "");
                        setNotes(item.notes ?? "");
                        setFormError("");
                      }}
                    >
                      编辑
                    </button>
                    <button disabled={busy} onClick={() => remove(item)}>
                      删除
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
        {shared ? (
          <details className="record-trend">
            <summary>查看体重趋势</summary>
            <p className="data-source-note">
              仅统计当前宠物的体重记录，不受记录列表的类型和日期筛选影响。
            </p>
            <WeightTrend
              key={scope}
              initialRange={trendRange}
              onRangeChange={setTrendRange}
              petId={
                scope !== "unlinked" &&
                !mismatch &&
                !petError &&
                pets.some((p) => p.id === scope)
                  ? scope
                  : null
              }
              petName={pets.find((p) => p.id === scope)?.name ?? "所选宠物"}
              revision={reload}
              onAdd={() => {
                if (dirty && !window.confirm("放弃当前草稿并添加体重记录？"))
                  return;
                reset();
                setType("weight");
                setFormOpen(true);
                document
                  .getElementById("record-weight")
                  ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
              }}
            />
          </details>
        ) : (
          <>
            <WeightTrend
              key={scope}
              initialRange={trendRange}
              onRangeChange={setTrendRange}
              petId={
                scope !== "unlinked" &&
                !mismatch &&
                !petError &&
                pets.some((p) => p.id === scope)
                  ? scope
                  : null
              }
              petName={pets.find((p) => p.id === scope)?.name ?? "所选宠物"}
              revision={reload}
              onAdd={() => {
                if (dirty && !window.confirm("放弃当前草稿并添加体重记录？"))
                  return;
                reset();
                setType("weight");
                setFormOpen(true);
                document
                  .getElementById("record-weight")
                  ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
              }}
            />
          </>
        )}
        <footer className="page-footer">
          <span>MADE FOR THE LITTLE ONES ♡</span>
          <span>宠爱，从了解开始。</span>
        </footer>
      </main>
    </>
  );
}
