import { useAppScope } from "../app/AppScope";
import { usingDemoData } from "../api/pets";
import AppIcon from "../components/navigation/AppIcon";
import PetSwitcher from "../components/navigation/PetSwitcher";
import { petSpeciesLabel } from "../lib/petLabel";
export default function MyPage() {
  const shared = useAppScope();
  if (!shared) return null;
  const pet = shared.pets.find((p) => p.id === shared.petId);
  return (
    <main className="page my-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">MY PET FAMILY</p>
          <h1>
            我的<span className="heading-dot">.</span>
          </h1>
          <p className="subtitle">照顾好每一个家庭成员。</p>
        </div>
      </header>
      <PetSwitcher />
      <p className="data-source-note">
        {usingDemoData
          ? "本地演示档案 · 仅保存在当前浏览器"
          : "后端档案 · 以服务端保存结果为准"}
      </p>
      <section className="family-panel" aria-label="我的宠物家庭">
        <div className="family-title">
          <div>
            <h2>我的宠物家庭</h2>
            <p>每一位，都是家人</p>
          </div>
          <span>{shared.pets.length} 位成员</span>
        </div>
        {shared.loading ? (
          <p role="status">正在加载成员…</p>
        ) : shared.error ? (
          <p>资料暂时无法加载，请在上方重试。</p>
        ) : shared.pets.length ? (
          <ul className="family-members">
            {shared.pets.map((p, i) => (
              <li key={p.id}>
                <span
                  className={`pet-initial avatar-${i % 3}`}
                  aria-hidden="true"
                >
                  {p.name.slice(0, 1)}
                </span>
                <strong>{p.name}</strong>
                <small>{p.breed || petSpeciesLabel(p)}</small>
                {p.id === shared.petId && <em>当前</em>}
              </li>
            ))}
          </ul>
        ) : (
          <p>还没有宠物档案，从第一位伙伴开始吧。</p>
        )}
        <button
          className="button secondary"
          onClick={shared.createPet}
          disabled={shared.loading || !!shared.error}
        >
          ＋ 新增宠物
        </button>
      </section>
      <section className="my-entries" aria-label="宠物生活功能">
        {(
          [
            [
              "pets",
              "宠物档案",
              pet
                ? `查看与编辑 · ${pet.name} · ${pet.breed || petSpeciesLabel(pet)}`
                : "选择宠物或创建档案",
            ],
            ["reminders", "待办提醒", "查看和管理宠物待办"],
            ["vlogs", "宠物 Vlog", "按宠物浏览图文与短视频时间线"],
            ["lost", "寻宠信息卡", "准备、预览与复制文字卡"],
          ] as const
        ).map(([id, title, description]) => (
          <button
            key={id}
            type="button"
            className={`my-entry entry-${id}`}
            onClick={() => shared.navigate(id)}
          >
            <span className="entry-icon">
              <AppIcon name={id} />
            </span>
            <span>
              <strong>{title}</strong>
              <small>{description}</small>
            </span>
            <span className="entry-arrow" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
      </section>
    </main>
  );
}
