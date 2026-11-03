import RecordsPage from "../pages/RecordsPage";
import RemindersPage from "../pages/RemindersPage";
import NearbyPage from "../pages/NearbyPage";
import { useState } from "react";
import type { AppPage } from "../components/common/AppHeader";
import ChatPage from "../pages/ChatPage";
import PetProfilePage from "../pages/PetProfilePage";

export default function App() {
  const [page, setPage] = useState<AppPage>("chat");

  return (
    <>
      <div hidden={page !== "chat"}>
        <ChatPage active={page === "chat"} onNavigate={setPage} />
      </div>
      {page === "records" && <RecordsPage onNavigate={setPage} />}
      {page === "reminders" && <RemindersPage onNavigate={setPage} />}
      {page === "nearby" && <NearbyPage onNavigate={setPage} />}
      <div hidden={page !== "pets"}>
        <PetProfilePage onNavigate={setPage} />
      </div>
    </>
  );
}
