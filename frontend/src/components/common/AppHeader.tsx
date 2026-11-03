export type AppPage = "chat" | "pets" | "records" | "reminders";

interface AppHeaderProps {
  active: AppPage;
  onNavigate: (page: AppPage) => void;
  navigationDisabled?: boolean;
}

export default function AppHeader({
  active,
  onNavigate,
  navigationDisabled = false,
}: AppHeaderProps) {
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
        <button
          type="button"
          className={active === "chat" ? "nav-item active" : "nav-item"}
          aria-current={active === "chat" ? "page" : undefined}
          disabled={navigationDisabled}
          onClick={() => onNavigate("chat")}
        >
          宠物助手
        </button>
        <button
          type="button"
          className={active === "pets" ? "nav-item active" : "nav-item"}
          aria-current={active === "pets" ? "page" : undefined}
          disabled={navigationDisabled}
          onClick={() => onNavigate("pets")}
        >
          宠物档案
        </button>
        <button
          type="button"
          className={active === "records" ? "nav-item active" : "nav-item"}
          aria-current={active === "records" ? "page" : undefined}
          disabled={navigationDisabled}
          onClick={() => onNavigate("records")}
        >
          日常记录
        </button>
        <button
          type="button"
          className={active === "reminders" ? "nav-item active" : "nav-item"}
          aria-current={active === "reminders" ? "page" : undefined}
          disabled={navigationDisabled}
          onClick={() => onNavigate("reminders")}
        >
          待办提醒
        </button>
      </nav>
    </header>
  );
}
