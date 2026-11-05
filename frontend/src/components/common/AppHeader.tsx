import { useAppScope } from "../../app/AppScope";
import AppIcon from "../navigation/AppIcon";
export type AppPage =
  "chat" | "pets" | "records" | "reminders" | "nearby" | "mine" | "lost";
interface AppHeaderProps {
  active: AppPage;
  onNavigate: (page: AppPage) => void;
  navigationDisabled?: boolean;
  shell?: boolean;
}
export default function AppHeader({
  active,
  onNavigate,
  navigationDisabled = false,
  shell = false,
}: AppHeaderProps) {
  const shared = useAppScope();
  if (shared && !shell) return null;
  return (
    <header className="topbar">
      <a className="brand" href="/" aria-label="Pet Agent 首页">
        <span className="brand-mark" aria-hidden="true">
          ✦
        </span>
        <span>
          pet<span className="brand-accent">agent</span>
          <small>你的宠物生活助手</small>
        </span>
      </a>
      <nav className="main-nav" aria-label="主要导航">
        {(
          [
            ["chat", "宠物助手"],
            ["pets", "宠物档案"],
            ["records", "日常记录"],
            ["reminders", "待办提醒"],
            ["nearby", "附近服务"],
            ["lost", "寻宠信息卡"],
            ["mine", "我的"],
          ] as [AppPage, string][]
        ).map(([id, title]) => (
          <button
            type="button"
            className={`nav-item ${active === id ? "active" : ""}`}
            aria-current={active === id ? "page" : undefined}
            disabled={navigationDisabled}
            onClick={() => onNavigate(id)}
            key={id}
          >
            {title}
          </button>
        ))}
      </nav>
    </header>
  );
}
export function AppBottomNav() {
  const shared = useAppScope();
  if (!shared) return null;
  return (
    <nav className="mobile-nav" aria-label="底部导航">
      {(
        [
          ["chat", "助手"],
          ["records", "记录"],
          ["reminders", "待办"],
          ["mine", "我的"],
        ] as const
      ).map(([id, label]) => {
        const active =
          shared.page === id ||
          (id === "mine" && ["pets", "nearby", "lost"].includes(shared.page));
        return (
          <button
            key={id}
            type="button"
            aria-current={active ? "page" : undefined}
            onClick={() => shared.navigate(id)}
          >
            <span>
              <AppIcon name={id} />
            </span>
            {label}
          </button>
        );
      })}
    </nav>
  );
}
