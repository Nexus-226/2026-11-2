import { useEffect, useState, type FormEvent } from "react";
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
  const [pets, setPets] = useState<Pet[]>([]),
    [scope, setScope] = useState("unlinked"),
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
  const [trendRange, setTrendRange] = useState("90");
  const mismatch = !usingDemoRecords && usingDemoData;
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
    setEditing(null);
    setType("deworming");
    setDate(shanghaiToday());
    setName("");
    setWeight("");
    setNotes("");
    setFormError("");
  }
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
        <header>
          <p>CARE JOURNAL</p>
          <h1>日常记录</h1>
          <p>保存已经发生的护理和体重变化。</p>
          <p className="records-source">
            {usingDemoRecords
              ? "本地演示数据 · 仅保存在当前浏览器，不同步后端"
              : "后端 API 数据 · 以服务端保存结果为准"}
          </p>
        </header>
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
        <section className="records-filters" aria-label="记录筛选">
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
          <label>
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
            reset();
            setType("weight");
            document
              .getElementById("record-weight")
              ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
          }}
        />
        <div className="records-layout">
          <section className="records-panel" id="record-weight">
            <h2>{editing ? "编辑记录" : "添加记录"}</h2>
            <p>
              当前：
              {scope === "unlinked"
                ? "未关联宠物"
                : (pets.find((p) => p.id === scope)?.name ?? "所选宠物")}
            </p>
            <form onSubmit={save}>
              <fieldset disabled={busy}>
                <label>
                  护理类型
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
                <label>
                  发生日期（上海时区）
                  <input
                    required
                    type="date"
                    max={shanghaiToday()}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </label>
                <label>
                  项目或产品名称
                  <input
                    maxLength={100}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                {type === "weight" && (
                  <label>
                    体重（kg）
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
                <label>
                  备注
                  <textarea
                    maxLength={2000}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </label>
                {formError && <p role="alert">{formError}</p>}
                <button type="submit">{busy ? "处理中…" : "保存记录"}</button>
                {editing && (
                  <button type="button" onClick={reset}>
                    取消编辑
                  </button>
                )}
              </fieldset>
            </form>
            <p role="status">{notice}</p>
          </section>
          <section className="records-panel" aria-label="记录时间线">
            <h2>记录时间线</h2>
            {loading ? (
              <p role="status">正在加载记录…</p>
            ) : error ? (
              <p role="alert">
                {error}
                <button onClick={() => setReload((v) => v + 1)}>重试</button>
              </p>
            ) : items.length === 0 ? (
              <p>当前筛选下暂无记录。</p>
            ) : (
              <ol>
                {items.map((item) => (
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
      </main>
    </>
  );
}
