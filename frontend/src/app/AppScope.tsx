import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { petClient } from "../api/pets";
import type { Pet } from "../types/pet";
import type { RecordDraft } from "../types/records";
import type { AppPage } from "../components/common/AppHeader";
export type Transition = "pet" | "page";
type Guard = {
  busy: boolean;
  warning: (transition: Transition) => string | null;
  onPetChange?: () => void;
  onLeave?: () => void;
};
interface AppScope {
  page: AppPage;
  petId: string | null;
  pets: Pet[];
  loading: boolean;
  error: string;
  notice: string;
  createVersion: number;
  creatingPet: boolean;
  recordDraft: RecordDraft | null;
  finishCreate: () => void;
  navigate: (page: AppPage) => boolean;
  selectPet: (id: string | null) => boolean;
  reloadPets: () => void;
  register: (id: string, guard: () => Guard) => () => void;
  authorize: (kind: Transition, exclude?: string) => boolean;
  publishPet: (pet: Pet, select?: boolean) => void;
  removePet: (id: string) => void;
  createPet: () => void;
  openRecordDraft: (draft: RecordDraft) => boolean;
  clearRecordDraft: () => void;
}
const Context = createContext<AppScope | null>(null);
export const useAppScope = () => useContext(Context);
export function useAppGuard(id: string, guard: Guard) {
  const scope = useAppScope(),
    latest = useRef(guard);
  latest.current = guard;
  const register = scope?.register;
  useEffect(() => register?.(id, () => latest.current), [id, register]);
}
export function AppScopeProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<AppPage>("chat"),
    [petId, setPetId] = useState<string | null>(null),
    [pets, setPets] = useState<Pet[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [reload, setReload] = useState(0),
    [createVersion, setCreateVersion] = useState(0),
    [creatingPet, setCreatingPet] = useState(false),
    [recordDraft, setRecordDraft] = useState<RecordDraft | null>(null);
  const guards = useRef(new Map<string, () => Guard>()),
    petsRef = useRef<Pet[]>([]),
    currentId = useRef<string | null>(null),
    epoch = useRef(0);
  const register = useCallback((id: string, get: () => Guard) => {
    guards.current.set(id, get);
    return () => {
      guards.current.delete(id);
    };
  }, []);
  function changeSelection(id: string | null) {
    if (id === currentId.current) return;
    for (const get of guards.current.values()) get().onPetChange?.();
    currentId.current = id;
    setPetId(id);
    // 切换或清空关联宠物后，旧记录草稿失效。
    setRecordDraft(null);
  }
  const authorize = useCallback((kind: Transition, exclude?: string) => {
    const entries = [...guards.current.entries()]
      .filter(([id]) => id !== exclude)
      .map(([, get]) => get());
    if (entries.some((g) => g.busy)) {
      setNotice("当前操作尚未结束，请等待完成或先取消等待。");
      return false;
    }
    const warnings = [
      ...new Set(entries.map((g) => g.warning(kind)).filter(Boolean)),
    ];
    return (
      !warnings.length || window.confirm(warnings.join("\n") + "\n是否继续？")
    );
  }, []);
  useEffect(() => {
    let live = true;
    const version = ++epoch.current;
    setLoading(true);
    setError("");
    petClient
      .list()
      .then((items) => {
        if (!live || version !== epoch.current) return;
        petsRef.current = items;
        setPets(items);
        // Loading a list never silently associates the first pet or clears a draft.
        if (
          currentId.current &&
          !items.some((p) => p.id === currentId.current)
        ) {
          changeSelection(null);
          setNotice("原宠物已不可用，已清空关联并开始新对话。");
        }
      })
      .catch((e) => {
        if (!live || version !== epoch.current) return;
        petsRef.current = [];
        setPets([]);
        changeSelection(null);
        setError(e instanceof Error ? e.message : "宠物资料加载失败。");
      })
      .finally(() => {
        if (live && version === epoch.current) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [reload]);
  function navigate(next: AppPage) {
    if (next === page) return true;
    if (!authorize("page")) return false;
    for (const get of guards.current.values()) get().onLeave?.();
    setNotice("");
    setCreatingPet(false);
    setPage(next);
    window.scrollTo?.({ top: 0 });
    return true;
  }
  function selectPet(id: string | null) {
    if (id === currentId.current) return true;
    if (id && !petsRef.current.some((p) => p.id === id)) {
      setNotice("宠物已不可用，请刷新档案后重试。");
      return false;
    }
    if (!authorize("pet")) return false;
    changeSelection(id);
    setNotice("当前宠物已更换，记录、待办与对话关联已同步。");
    return true;
  }
  function publishPet(pet: Pet, select = false) {
    epoch.current++;
    const next = petsRef.current.some((p) => p.id === pet.id)
      ? petsRef.current.map((p) => (p.id === pet.id ? pet : p))
      : [...petsRef.current, pet];
    petsRef.current = next;
    setPets(next);
    setLoading(false);
    setError("");
    if (select) changeSelection(pet.id);
  }
  function removePet(id: string) {
    epoch.current++;
    petsRef.current = petsRef.current.filter((p) => p.id !== id);
    setPets(petsRef.current);
    setLoading(false);
    if (currentId.current === id) changeSelection(null);
  }
  function createPet() {
    if (!authorize("page")) return;
    for (const get of guards.current.values()) get().onLeave?.();
    setCreateVersion((v) => v + 1);
    setCreatingPet(true);
    setPage("pets");
    setNotice("");
  }
  function openRecordDraft(draft: RecordDraft) {
    if (!authorize("page")) return false;
    for (const get of guards.current.values()) get().onLeave?.();
    setRecordDraft(draft);
    setNotice("");
    setCreatingPet(false);
    setPage("records");
    window.scrollTo?.({ top: 0 });
    return true;
  }
  function clearRecordDraft() {
    setRecordDraft(null);
  }
  return (
    <Context.Provider
      value={{
        page,
        petId,
        pets,
        loading,
        error,
        notice,
        createVersion,
        creatingPet,
        recordDraft,
        finishCreate: () => setCreatingPet(false),
        navigate,
        selectPet,
        reloadPets: () => setReload((v) => v + 1),
        register,
        authorize,
        publishPet,
        removePet,
        createPet,
        openRecordDraft,
        clearRecordDraft,
      }}
    >
      {children}
    </Context.Provider>
  );
}
