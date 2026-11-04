import { useEffect, useState, type FormEvent } from "react";
import { petClient, usingDemoData } from "../api/pets";
import AppHeader, { type AppPage } from "../components/common/AppHeader";
import type { Pet, PetInput, PetSpecies } from "../types/pet";
import { normalizeOtherSpecies } from "../lib/petSpecies";

type FormValues = {
  name: string;
  species: PetSpecies;
  other_species: string;
  breed: string;
  birthday: string;
  notes: string;
};
const emptyForm: FormValues = {
  name: "",
  species: "dog",
  other_species: "",
  breed: "",
  birthday: "",
  notes: "",
};
const speciesLabels: Record<PetSpecies, string> = {
  dog: "狗狗",
  cat: "猫咪",
  other: "其他",
};

function speciesLabel(pet: Pet): string {
  return pet.species === "other" && pet.other_species
    ? `其他（${pet.other_species}）`
    : speciesLabels[pet.species];
}

function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function formFromPet(pet: Pet): FormValues {
  return {
    name: pet.name,
    species: pet.species,
    other_species: pet.other_species ?? "",
    breed: pet.breed ?? "",
    birthday: pet.birthday ?? "",
    notes: pet.notes ?? "",
  };
}

function normalize(form: FormValues): PetInput {
  return {
    name: form.name.trim(),
    species: form.species,
    other_species:
      form.species === "other"
        ? normalizeOtherSpecies(form.other_species)
        : null,
    breed: form.breed.trim() || null,
    birthday: form.birthday || null,
    notes: form.notes.trim() || null,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试。";
}

export default function PetProfilePage({
  onNavigate,
}: {
  onNavigate: (page: AppPage) => void;
}) {
  const [pets, setPets] = useState<Pet[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<FormValues>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    petClient
      .list()
      .then((items) => {
        if (!active) return;
        setPets(items);
        setSelectedId(items[0]?.id ?? null);
        setForm(items[0] ? formFromPet(items[0]) : emptyForm);
        setCreating(items.length === 0);
      })
      .catch((error: unknown) => {
        if (active) setLoadError(errorMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const selectedPet = pets.find((pet) => pet.id === selectedId);

  function canLeaveForm() {
    const baseline = creating
      ? emptyForm
      : selectedPet
        ? formFromPet(selectedPet)
        : emptyForm;
    return (
      JSON.stringify(form) === JSON.stringify(baseline) ||
      window.confirm("当前修改尚未保存，确定放弃吗？")
    );
  }

  function choosePet(pet: Pet) {
    if (!canLeaveForm()) return;
    setSelectedId(pet.id);
    setForm(formFromPet(pet));
    setCreating(false);
    setFormError("");
    setNotice("");
  }

  function startCreate() {
    if (!canLeaveForm()) return;
    setSelectedId(null);
    setForm({ ...emptyForm });
    setCreating(true);
    setFormError("");
    setNotice("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = normalize(form);
    if (!input.name) {
      setFormError("请填写宠物名字。");
      return;
    }
    if (input.other_species && [...input.other_species].length > 50) {
      setFormError("具体物种最多填写 50 个字符。");
      return;
    }
    if (input.birthday && input.birthday > localToday()) {
      setFormError("生日不能晚于今天。");
      return;
    }
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      const saved = creating
        ? await petClient.create(input)
        : await petClient.update(selectedId!, input);
      setPets((current) =>
        creating
          ? [...current, saved]
          : current.map((pet) => (pet.id === saved.id ? saved : pet)),
      );
      setSelectedId(saved.id);
      setForm(formFromPet(saved));
      setCreating(false);
      setNotice(creating ? "宠物资料已创建。" : "宠物资料已保存。");
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (
      !selectedPet ||
      !window.confirm(`确定删除「${selectedPet.name}」的资料吗？`)
    )
      return;
    setBusy(true);
    setFormError("");
    setNotice("");
    try {
      await petClient.remove(selectedPet.id);
      const remaining = pets.filter((pet) => pet.id !== selectedPet.id);
      setPets(remaining);
      setSelectedId(remaining[0]?.id ?? null);
      setForm(remaining[0] ? formFromPet(remaining[0]) : { ...emptyForm });
      setCreating(remaining.length === 0);
      setNotice("宠物资料已删除。");
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <AppHeader
        active="pets"
        navigationDisabled={busy}
        onNavigate={(page) => {
          if (page === "pets") return;
          if (canLeaveForm()) {
            setForm(selectedPet ? formFromPet(selectedPet) : { ...emptyForm });
            setFormError("");
            setNotice("");
            onNavigate(page);
          }
        }}
      />

      <main className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true">✳</span> &nbsp; PET PROFILE
            </p>
            <h1>
              给它一份专属档案<span className="heading-dot">.</span>
            </h1>
            <p className="subtitle">记下关于它的小细节，让每一次陪伴更贴心。</p>
          </div>
          <span className="heading-illustration" aria-hidden="true">
            ♡<span>✦</span>
          </span>
        </div>

        <div
          className={`mode-banner ${usingDemoData ? "demo" : "connected"}`}
          role="status"
        >
          <span className="mode-dot" aria-hidden="true" />
          <div>
            <strong>
              {usingDemoData ? "当前为本地演示模式" : "当前为后端接口模式"}
            </strong>
            <span>
              {usingDemoData
                ? "资料仅保存在此浏览器，不会同步到服务器。"
                : "资料通过后端接口读取与保存。"}
            </span>
          </div>
        </div>

        {loading ? (
          <section className="state-card" role="status">
            <span className="spinner" aria-hidden="true" /> 正在加载宠物资料…
          </section>
        ) : loadError ? (
          <section className="state-card error-state" role="alert">
            <strong>资料暂时无法加载</strong>
            <p>{loadError}</p>
            <button
              className="button secondary"
              onClick={() => setReloadKey((value) => value + 1)}
            >
              重新加载
            </button>
          </section>
        ) : (
          <div className="workspace">
            <aside className="pet-list-panel" aria-label="宠物列表">
              <div className="panel-title">
                <div>
                  <span className="section-kicker">MY COMPANIONS</span>
                  <h2>
                    我的伙伴 <span>{pets.length}</span>
                  </h2>
                </div>
              </div>
              {pets.length === 0 ? (
                <div className="empty-list">
                  <span className="empty-icon" aria-hidden="true">
                    ♡
                  </span>
                  <strong>还没有宠物档案</strong>
                  <p>从第一份资料开始，记录你们的故事。</p>
                </div>
              ) : (
                <div className="pet-list">
                  {pets.map((pet, index) => (
                    <button
                      key={pet.id}
                      type="button"
                      className={`pet-card ${!creating && selectedId === pet.id ? "active" : ""}`}
                      onClick={() => choosePet(pet)}
                      disabled={busy}
                      aria-pressed={!creating && selectedId === pet.id}
                    >
                      <span
                        className={`pet-avatar avatar-${index % 3}`}
                        aria-hidden="true"
                      >
                        {pet.species === "cat"
                          ? "猫"
                          : pet.species === "dog"
                            ? "犬"
                            : "宠"}
                      </span>
                      <span className="pet-card-text">
                        <strong>{pet.name}</strong>
                        <small>
                          {speciesLabel(pet)}
                          {pet.breed ? ` · ${pet.breed}` : ""}
                        </small>
                      </span>
                      <span className="pet-arrow" aria-hidden="true">
                        ↗
                      </span>
                    </button>
                  ))}
                </div>
              )}
              <button
                type="button"
                className="add-pet"
                onClick={startCreate}
                disabled={busy}
              >
                <span aria-hidden="true">＋</span> 添加新伙伴
              </button>
              <p className="panel-note">
                <span aria-hidden="true">✿</span> &nbsp;
                每个小家伙都值得被认真了解。
              </p>
            </aside>

            <section className="form-panel" aria-labelledby="form-title">
              <div className="form-heading">
                <div>
                  <span className="section-kicker">THE LITTLE DETAILS</span>
                  <h2 id="form-title">
                    {creating ? "新建宠物档案" : "宠物资料"}
                  </h2>
                  <p>
                    {creating
                      ? "从名字开始，认识你的新伙伴。"
                      : `随时更新关于它的重要信息。${selectedPet ? ` · ${speciesLabel(selectedPet)}` : ""}`}
                  </p>
                </div>
                <span className="form-flower" aria-hidden="true">
                  ✽
                </span>
              </div>

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

              <form onSubmit={handleSubmit}>
                <fieldset className="field-grid" disabled={busy}>
                  <label className="field">
                    <span>
                      宠物名字 <em>*</em>
                    </span>
                    <input
                      autoComplete="off"
                      maxLength={50}
                      required
                      placeholder="例如：豆豆"
                      value={form.name}
                      onChange={(event) =>
                        setForm({ ...form, name: event.target.value })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>
                      宠物类型 <em>*</em>
                    </span>
                    <select
                      value={form.species}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          species: event.target.value as PetSpecies,
                          other_species:
                            event.target.value === "other"
                              ? form.other_species
                              : "",
                        })
                      }
                    >
                      <option value="dog">狗狗</option>
                      <option value="cat">猫咪</option>
                      <option value="other">其他</option>
                    </select>
                  </label>
                  {form.species === "other" && (
                    <label className="field field-wide">
                      <span>
                        具体物种 <small>选填</small>
                      </span>
                      <input
                        autoComplete="off"
                        placeholder="例如：兔、仓鼠、鹦鹉"
                        aria-describedby="other-species-hint"
                        value={form.other_species}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            other_species: event.target.value,
                          })
                        }
                      />
                      <small className="field-hint" id="other-species-hint">
                        可留空，最多填写 50 个字符。
                      </small>
                    </label>
                  )}
                  <label className="field">
                    <span>
                      品种 <small>选填</small>
                    </span>
                    <input
                      maxLength={100}
                      placeholder="例如：金毛"
                      value={form.breed}
                      onChange={(event) =>
                        setForm({ ...form, breed: event.target.value })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>
                      生日 <small>选填</small>
                    </span>
                    <input
                      type="date"
                      max={localToday()}
                      value={form.birthday}
                      onChange={(event) =>
                        setForm({ ...form, birthday: event.target.value })
                      }
                    />
                  </label>
                  <label className="field field-wide">
                    <span>
                      健康与生活备注 <small>选填</small>
                    </span>
                    <textarea
                      rows={5}
                      maxLength={2000}
                      placeholder="过敏情况、饮食习惯，或你想记住的任何事情…"
                      value={form.notes}
                      onChange={(event) =>
                        setForm({ ...form, notes: event.target.value })
                      }
                    />
                    <small className="field-hint">
                      这些细节会帮助你更好地照顾它。
                    </small>
                  </label>
                </fieldset>
                <div className="form-actions">
                  <button
                    className="button primary"
                    type="submit"
                    disabled={busy}
                  >
                    {busy ? "处理中…" : creating ? "创建档案" : "保存修改"}{" "}
                    <span aria-hidden="true">↗</span>
                  </button>
                  {!creating && (
                    <button
                      className="button delete"
                      type="button"
                      onClick={handleDelete}
                      disabled={busy}
                    >
                      删除档案
                    </button>
                  )}
                  {creating && pets.length > 0 && (
                    <button
                      className="button text-button"
                      type="button"
                      onClick={() => choosePet(pets[0])}
                      disabled={busy}
                    >
                      取消
                    </button>
                  )}
                </div>
              </form>
            </section>
          </div>
        )}
        <footer className="page-footer">
          <span>MADE FOR THE LITTLE ONES ♡</span>
          <span>宠爱，从了解开始。</span>
        </footer>
      </main>
    </div>
  );
}
