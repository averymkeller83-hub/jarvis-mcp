import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { api } from "../api/client";

interface PersonalityContextValue {
  assistantName: string;
  userName: string;
  loading: boolean;
  refresh: () => Promise<void>;
}

const PersonalityContext = createContext<PersonalityContextValue>({
  assistantName: "JARVIS",
  userName: "Sir",
  loading: true,
  refresh: async () => {},
});

export function PersonalityProvider({ children }: { children: ReactNode }) {
  const [assistantName, setAssistantName] = useState("JARVIS");
  const [userName, setUserName] = useState("Sir");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api<Record<string, Record<string, unknown>>>("/settings");
      const p = data.personality ?? {};
      if (p.assistant_name) setAssistantName(p.assistant_name as string);
      if (p.user_display_name) setUserName(p.user_display_name as string);
    } catch {
      // Keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <PersonalityContext.Provider value={{ assistantName, userName, loading, refresh }}>
      {children}
    </PersonalityContext.Provider>
  );
}

export function usePersonality(): PersonalityContextValue {
  return useContext(PersonalityContext);
}
