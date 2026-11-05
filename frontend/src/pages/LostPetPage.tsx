import { useState } from "react";
import { useAppGuard, useAppScope } from "../app/AppScope";
import PetSwitcher from "../components/navigation/PetSwitcher";
import { petSpeciesLabel } from "../lib/petLabel";
import { shanghaiToday } from "../types/records";
export default function LostPetPage() {
  const shared = useAppScope(),
    [date, setDate] = useState(""),
    [place, setPlace] = useState(""),
    [contact, setContact] = useState(""),
    [description, setDescription] = useState(""),
    [notice, setNotice] = useState("");
  const pet = shared?.pets.find((p) => p.id === shared.petId);
  function reset() {
    setDate("");
    setPlace("");
    setContact("");
    setDescription("");
    setNotice("");
  }
  const dirty = !!date || !!place || !!contact || !!description;
  useAppGuard("lost", {
    busy: false,
    warning: () =>
      dirty ? "离开将清空此页寻宠信息，请先复制需要保留的内容。" : null,
    onPetChange: reset,
  });
  const text = pet
    ? [
        "寻宠信息",
        `宠物：${pet.name}`,
        `类型：${petSpeciesLabel(pet)}`,
        pet.breed && `品种：${pet.breed}`,
        description.trim() && `外貌特征：${description.trim()}`,
        date && `走失日期：${date}`,
        place.trim() && `走失地点：${place.trim()}`,
        contact.trim() && `联系方式：${contact.trim()}`,
        "如有线索，请与联系人核实。",
      ]
        .filter(Boolean)
        .join("\n")
    : "";
  return (
    <main className="page lost-page">
      <button className="back-link" onClick={() => shared?.navigate("mine")}>
        ‹ 返回我的
      </button>
      <header className="page-heading">
        <div>
          <p className="eyebrow">BRING THEM HOME</p>
          <h1>
            寻宠信息卡<span className="heading-dot">.</span>
          </h1>
          <p className="subtitle">整理关键信息，让牵挂被看见。</p>
        </div>
      </header>
      <PetSwitcher label="制作信息卡的宠物" />
      {!pet ? (
        <section className="state-card">
          <h2>请先选择一只宠物</h2>
          <p>在上方选择宠物后，即可填写并预览信息卡。</p>
        </section>
      ) : (
        <div className="lost-layout">
          <section className="form-panel">
            <h2>填写信息</h2>
            <p>以下字段均可选，未填写的内容会自动省略。</p>
            <form>
              <label className="field">
                外貌特征
                <textarea
                  rows={3}
                  maxLength={1000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <label className="field">
                走失日期
                <input
                  type="date"
                  max={shanghaiToday()}
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>
              <label className="field">
                走失地点
                <input
                  maxLength={200}
                  value={place}
                  onChange={(e) => setPlace(e.target.value)}
                />
              </label>
              <label className="field">
                联系方式
                <input
                  maxLength={120}
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                />
              </label>
            </form>
          </section>
          <section className="form-panel" aria-label="寻宠信息卡预览">
            <h2>信息卡预览</h2>
            <pre className="lost-text">{text}</pre>
            <button
              className="button primary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(text);
                  setNotice("文字已复制，未进行公开发布。");
                } catch {
                  setNotice("浏览器未允许自动复制，可选中下方文本手动复制。");
                }
              }}
            >
              复制文字卡
            </button>
            <label className="field">
              可复制文本
              <textarea readOnly rows={8} value={text} />
            </label>
            {notice && <p role="status">{notice}</p>}
          </section>
        </div>
      )}
      <p className="data-source-note">
        信息仅在当前页面内存保存，不公开发布；复制后分享前请核对内容与联系方式。本功能不提供定位、找回或图片导出。
      </p>
    </main>
  );
}
