import { createContext, useContext, useState, useCallback, useRef } from "react";
import { fetchChatHistory, clearChatHistory as apiClearHistory } from "../api/chat";

export interface Message {
  id: number;
  role: "user" | "jarvis";
  text: string;
  surface?: string;
  timestamp: Date;
}

interface ChatStore {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  loaded: boolean;
  loadHistory: (userName: string, assistantName: string) => void;
  clearMessages: (userName: string) => void;
}

const ChatContext = createContext<ChatStore | null>(null);

function makeGreeting(userName: string, assistantName: string): Message {
  return {
    id: Date.now(),
    role: "jarvis",
    text: `Good day, ${userName}. I'm ${assistantName} — created by Avery Keller, inspired by the vision of Jarvis from Iron Man, and powered by Claude.

I'm here to make your life easier. The more you share with me, the better I get — think of us as a team that sharpens each other.

Here's a taste of what I can help with:
- Finding and applying to jobs that match your skills
- Learning new things — I'll quiz you, find resources, track progress
- Meal planning and grocery lists for the week
- Staying on top of deadlines at work or school
- Morning briefings so you start every day prepared
- Watching your projects for issues, PRs, and things that need attention

To get started, I'd love to know just one thing:

What's something you wish you had more time for?

That'll tell me a lot about where I can help first. And don't worry — I'll always follow up with questions so you stay in the driver's seat. Nothing happens without you saying so.`,
    timestamp: new Date(),
  };
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loaded, setLoaded] = useState(false);
  const loadingRef = useRef(false);

  const loadHistory = useCallback((userName: string, assistantName: string) => {
    if (loaded || loadingRef.current) return;
    loadingRef.current = true;

    fetchChatHistory(200)
      .then((res) => {
        if (res.messages.length > 0) {
          setMessages(
            res.messages.map((m, i) => ({
              id: i,
              role: m.role === "user" ? ("user" as const) : ("jarvis" as const),
              text: m.text,
              surface: m.surface,
              timestamp: new Date(m.timestamp),
            })),
          );
        } else {
          setMessages([makeGreeting(userName, assistantName)]);
        }
      })
      .catch(() => {
        setMessages([makeGreeting(userName, assistantName)]);
      })
      .finally(() => {
        setLoaded(true);
        loadingRef.current = false;
      });
  }, [loaded]);

  const clearMessages = useCallback((userName: string) => {
    apiClearHistory().catch(() => {});
    setMessages([{
      id: Date.now(),
      role: "jarvis",
      text: `Chat cleared. How can I help you, ${userName}?`,
      timestamp: new Date(),
    }]);
  }, []);

  return (
    <ChatContext.Provider value={{ messages, setMessages, loaded, loadHistory, clearMessages }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat(): ChatStore {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be inside ChatProvider");
  return ctx;
}
