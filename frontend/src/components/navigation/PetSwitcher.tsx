import { useId, useRef, useState } from "react";
import { useAppScope } from "../../app/AppScope";
import { petSpeciesLabel as speciesLabel } from "../../lib/petLabel";
import AppIcon from "./AppIcon";
export default function PetSwitcher({
  disabled = false,
  label = "当前宠物",
  unlinked = false,
}: {
  disabled?: boolean;
  label?: string;
  unlinked?: boolean;
}) {
  const scope = useAppScope(),
    dialog = useRef<HTMLDialogElement>(null),
    [pending, setPending] = useState<string | null>(null),
    [open, setOpen] = useState(false);
  const groupName = useId();
  if (!scope) return null;
  const current = unlinked ? null : scope.petId,
    pet = scope.pets.find((p) => p.id === current);
  return (
    <section className="pet-scope" aria-label="当前宠物范围">
      <button
        className="pet-switch"
        type="button"
        disabled={disabled || scope.loading || !!scope.error}
        aria-label={`当前宠物：${pet ? `${pet.name} · ${pet.breed || speciesLabel(pet)}` : "未关联宠物"}，点击切换`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setPending(current);
          dialog.current?.showModal();
          setOpen(true);
        }}
      >
        <span className="pet-initial" aria-hidden="true">
          {pet?.name.slice(0, 1) || "＋"}
        </span>
        <span className="pet-switch-text">
          <small>{label}</small>
          <strong>
            {scope.loading
              ? "正在加载档案…"
              : pet
                ? `${pet.name} · ${pet.breed || speciesLabel(pet)}`
                : "未关联宠物"}
          </strong>
        </span>
        <span className={`pet-switch-action ${open ? "expanded" : ""}`}>
          切换
          <AppIcon name="chevron" />
        </span>
      </button>
      {scope.error && (
        <p role="alert">
          宠物资料加载失败：{scope.error}
          <button onClick={scope.reloadPets}>重试加载</button>
        </p>
      )}
      <dialog
        ref={dialog}
        className="pet-picker"
        aria-label="切换当前宠物"
        onClose={() => setOpen(false)}
        onCancel={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        <div className="pet-picker-heading">
          <div>
            <span className="section-kicker">EACH ONE MATTERS</span>
            <h2>这次，照顾哪一位？</h2>
          </div>
          <button
            type="button"
            aria-label="关闭宠物选择"
            onClick={() => dialog.current?.close()}
          >
            ×
          </button>
        </div>
        <fieldset>
          <legend>选择当前宠物</legend>
          {scope.pets.map((p) => (
            <label className={pending === p.id ? "selected" : ""} key={p.id}>
              <span className="pet-initial" aria-hidden="true">
                {p.name.slice(0, 1)}
              </span>
              <span>
                <strong>
                  {p.name} · {p.breed || speciesLabel(p)}
                </strong>
                <small>
                  {speciesLabel(p)} · 生日 {p.birthday || "未填写"}
                </small>
              </span>
              <input
                type="radio"
                name={groupName}
                checked={pending === p.id}
                onChange={() => setPending(p.id)}
              />
            </label>
          ))}
          <label className={pending === null ? "selected" : ""}>
            <span>
              <strong>未关联宠物</strong>
              <small>查看未关联记录、待办或开始通用对话</small>
            </span>
            <input
              type="radio"
              name={groupName}
              checked={pending === null}
              onChange={() => setPending(null)}
            />
          </label>
        </fieldset>
        <p>
          确认后将同步记录、待办和对话关联。已有对话将开始新会话；未保存的修改会提醒确认。
        </p>
        <div className="pet-picker-actions">
          <button type="button" onClick={() => dialog.current?.close()}>
            取消
          </button>
          <button
            type="button"
            className="button primary"
            onClick={() => {
              if (scope.selectPet(pending)) dialog.current?.close();
            }}
          >
            {pending === current ? "保持当前宠物" : "确认切换"}
          </button>
        </div>
      </dialog>
    </section>
  );
}
