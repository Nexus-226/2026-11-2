import RecordsPage from "../pages/RecordsPage";
import VlogPage from "../pages/VlogPage";
import RemindersPage from "../pages/RemindersPage";
import NearbyPage from "../pages/NearbyPage";
import ChatPage from "../pages/ChatPage";
import PetProfilePage from "../pages/PetProfilePage";
import MyPage from "../pages/MyPage";
import LostPetPage from "../pages/LostPetPage";
import AppHeader, { AppBottomNav } from "../components/common/AppHeader";
import { AppScopeProvider, useAppScope } from "./AppScope";
import "../styles/mobile-shell.css";
function AppContent() {
  const shared = useAppScope()!;
  const { page, navigate } = shared;
  return (
    <div className="app-layout">
      <AppHeader active={page} onNavigate={navigate} shell />
      {shared.notice && (
        <div className="app-notice" role="status">
          {shared.notice}
        </div>
      )}
      <div hidden={page !== "chat"}>
        <ChatPage active={page === "chat"} onNavigate={navigate} />
      </div>
      {page === "records" && <RecordsPage onNavigate={navigate} />}{" "}
      {page === "vlogs" && <VlogPage onNavigate={navigate} />}{" "}
      {page === "reminders" && <RemindersPage onNavigate={navigate} />}{" "}
      {page === "nearby" && <NearbyPage onNavigate={navigate} />}{" "}
      {page === "pets" && <PetProfilePage onNavigate={navigate} />}{" "}
      {page === "mine" && <MyPage />} {page === "lost" && <LostPetPage />}
      <AppBottomNav />
    </div>
  );
}
export default function App() {
  return (
    <AppScopeProvider>
      <AppContent />
    </AppScopeProvider>
  );
}
