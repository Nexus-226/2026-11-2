import { useAppGuard, useAppScope } from "../app/AppScope";
import PetSwitcher from "../components/navigation/PetSwitcher";
import { useEffect, useRef, useState, type FormEvent } from "react";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import { petClient } from "../api/pets";
import { vlogClient } from "../api/vlogs";
import { shanghaiToday } from "../types/records";
import type { Pet } from "../types/pet";
import type { Vlog } from "../types/vlog";
import "../styles/records.css";
import "../styles/vlog.css";

const MAX_IMAGES = 3;
const IMAGE_LIMIT = 5 * 1024 * 1024;
const VIDEO_LIMIT = 20 * 1024 * 1024;
const msg = (e: unknown) =>
  e instanceof Error ? e.message : "操作失败，请重试。";

function precheck(files: File[]): string | null {
  if (files.length > MAX_IMAGES) return "每篇最多上传 3 张图片。";
  const images = files.filter((f) => f.type.startsWith("image/"));
  const videos = files.filter((f) => f.type === "video/mp4");
  if (images.length + videos.length !== files.length)
    return "仅支持 JPEG/PNG 图片或 MP4 视频。";
  if (images.length && videos.length)
    return "同一篇只能全部是图片或是一段视频，不能混合。";
  if (videos.length > 1) return "每篇最多上传 1 段视频。";
  if (images.some((f) => f.size > IMAGE_LIMIT))
    return "单张图片不能超过 5 MB。";
  if (videos.some((f) => f.size > VIDEO_LIMIT)) return "视频不能超过 20 MB。";
  return null;
}

export default function VlogPage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const shared = useAppScope();
  const [pets, setPets] = useState<Pet[]>([]),
    [localScope, setLocalScope] = useState(""),
    [items, setItems] = useState<Vlog[]>([]);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [petError, setPetError] = useState(""),
    [formError, setFormError] = useState(""),
    [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Vlog | null>(null),
    [date, setDate] = useState(shanghaiToday),
    [caption, setCaption] = useState(""),
    [selected, setSelected] = useState<File[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const scope = shared ? shared.petId || "" : localScope;
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
        if (live) setPets(p);
      })
      .catch((e) => {
        if (live) setPetError(msg(e));
      });
    return () => {
      live = false;
    };
  }, [shared?.pets, shared?.error]);
  useEffect(() => {
    if (!scope) {
      setItems([]);
      setLoading(false);
      setError("");
      return;
    }
    let live = true;
    setLoading(true);
    setError("");
    vlogClient
      .list({ pet_id: scope })
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
  function reset() {
    setFormOpen(false);
    setEditing(null);
    setDate(shanghaiToday());
    setCaption("");
    setSelected([]);
    if (fileRef.current) fileRef.current.value = "";
    setFormError("");
  }
  const dirty =
    !!editing ||
    caption !== "" ||
    date !== shanghaiToday() ||
    selected.length > 0;
  useAppGuard("vlogs", {
    busy,
    warning: () => (dirty ? "Vlog 内容尚未保存，继续将丢弃草稿。" : null),
    onPetChange: reset,
    onLeave: reset,
  });
  async function save(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    setNotice("");
    if (!scope) {
      setFormError("请先选择宠物。");
      return;
    }
    if (!date || date > shanghaiToday()) {
      setFormError("日期不能晚于上海时区今天。");
      return;
    }
    if (!editing) {
      const problem = precheck(selected);
      if (problem) {
        setFormError(problem);
        return;
      }
    }
    setBusy(true);
    try {
      if (editing) {
        await vlogClient.update(editing.id, {
          caption: caption.trim() || null,
          occurred_on: date,
        });
      } else {
        await vlogClient.create(
          { pet_id: scope, occurred_on: date, caption: caption.trim() || null },
          selected,
        );
      }
      reset();
      setNotice("Vlog 已保存。");
      setReload((v) => v + 1);
    } catch (err) {
      setFormError(msg(err));
    } finally {
      setBusy(false);
    }
  }
  async function remove(item: Vlog) {
    if (!window.confirm("删除这篇 Vlog？媒体文件会一并回收。")) return;
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      await vlogClient.remove(item.id);
      if (editing?.id === item.id) reset();
      setNotice("Vlog 已删除。");
      setReload((v) => v + 1);
    } catch (err) {
      setFormError(msg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <AppHeader
        active="vlogs"
        onNavigate={onNavigate}
        navigationDisabled={busy}
      />
      <main className="vlog-page">
        <header className="page-heading">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true">✳</span> &nbsp; PET VLOG
            </p>
            <h1>
              宠物 Vlog<span className="heading-dot">.</span>
            </h1>
            <p className="subtitle">用图文和短视频，记下相伴的每一天。</p>
          </div>
          <span className="heading-illustration" aria-hidden="true">
            ♡<span>✦</span>
          </span>
        </header>
        <PetSwitcher label="当前宠物" disabled={busy} />
        {!shared && (
          <label>
            当前宠物
            <select
              disabled={busy}
              value={localScope}
              onChange={(e) => {
                setLocalScope(e.target.value);
                reset();
                setNotice("");
              }}
            >
              <option value="">选择宠物</option>
              {pets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="data-source-note">
          后端保存 · 媒体存放在本机私有目录，删除后不可访问
        </p>
        {!scope && <p role="status">选择宠物后查看它的 Vlog 时间线。</p>}
        {petError && (
          <p role="alert">
            宠物列表加载失败：{petError}
            <button onClick={() => setReload((v) => v + 1)}>重试</button>
          </p>
        )}
        {notice && (
          <div className="notice success" role="status">
            {notice}
          </div>
        )}
        {formError && (
          <div className="notice error" role="alert">
            {formError}
          </div>
        )}
        {scope && (
          <section className="vlog-panel" aria-label="Vlog 时间线">
            <div className="form-heading">
              <div>
                <span className="section-kicker">TIMELINE</span>
                <h2>
                  {`${pets.find((p) => p.id === scope)?.name ?? "所选宠物"}的时间线`}
                </h2>
              </div>
              <button
                className="button primary"
                disabled={busy}
                onClick={() => {
                  if (!dirty || window.confirm("放弃当前草稿并新建 Vlog？")) {
                    reset();
                    setFormOpen(true);
                  }
                }}
              >
                ＋ 新建 Vlog
              </button>
            </div>
            {formOpen && (
              <section className="form-panel care-form is-open">
                <form onSubmit={save}>
                  <fieldset className="field-grid" disabled={busy}>
                    <label className="field">
                      <span>日期</span>
                      <input
                        required
                        type="date"
                        max={shanghaiToday()}
                        value={date}
                        onChange={(e) => setDate(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>文案</span>
                      <textarea
                        maxLength={2000}
                        rows={3}
                        value={caption}
                        onChange={(e) => setCaption(e.target.value)}
                      />
                    </label>
                    {!editing && (
                      <label className="field">
                        <span>媒体（选传，最多 3 张图或 1 段视频）</span>
                        <input
                          ref={fileRef}
                          type="file"
                          multiple
                          accept="image/jpeg,image/png,video/mp4"
                          onChange={(e) =>
                            setSelected(Array.from(e.target.files ?? []))
                          }
                        />
                      </label>
                    )}
                    {editing && (
                      <p className="vlog-media-hint">
                        首版不支持替换媒体；如需更换，请删除这篇后重新创建。
                      </p>
                    )}
                  </fieldset>
                  <div className="vlog-form-actions">
                    <button className="button primary" disabled={busy}>
                      {editing ? "保存修改" : "保存 Vlog"}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busy}
                      onClick={() => {
                        if (!dirty || window.confirm("放弃未保存的内容？"))
                          reset();
                      }}
                    >
                      取消
                    </button>
                  </div>
                </form>
              </section>
            )}
            {loading ? (
              <p role="status">正在加载 Vlog…</p>
            ) : error ? (
              <p role="alert">
                {error}
                <button disabled={busy} onClick={() => setReload((v) => v + 1)}>
                  重试
                </button>
              </p>
            ) : items.length ? (
              <ol className="vlog-timeline">
                {items.map((item) => (
                  <li key={item.id} className="vlog-entry">
                    <div className="vlog-entry-head">
                      <time dateTime={item.occurred_on}>
                        {item.occurred_on}
                      </time>
                      <small>{item.media.length} 个媒体</small>
                    </div>
                    {item.caption && (
                      <p className="record-notes">{item.caption}</p>
                    )}
                    {item.media.length > 0 && (
                      <div className="vlog-media-grid">
                        {item.media.map((m) =>
                          m.media_type === "video" ? (
                            <video
                              key={m.id}
                              controls
                              preload="metadata"
                              src={m.url}
                              aria-label={m.filename}
                            />
                          ) : (
                            <img
                              key={m.id}
                              loading="lazy"
                              src={m.url}
                              alt={m.filename}
                            />
                          ),
                        )}
                      </div>
                    )}
                    <div className="vlog-entry-actions">
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (
                            dirty &&
                            !window.confirm("放弃当前草稿并编辑这篇？")
                          )
                            return;
                          setFormOpen(true);
                          setEditing(item);
                          setDate(item.occurred_on);
                          setCaption(item.caption ?? "");
                          setFormError("");
                        }}
                      >
                        编辑
                      </button>
                      <button disabled={busy} onClick={() => remove(item)}>
                        删除
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p>当前宠物还没有 Vlog，从第一篇开始吧。</p>
            )}
          </section>
        )}
        <footer className="page-footer">
          <span>MADE FOR THE LITTLE ONES ♡</span>
          <span>宠爱，从了解开始。</span>
        </footer>
      </main>
    </>
  );
}
