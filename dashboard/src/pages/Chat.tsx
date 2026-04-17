import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useToast } from "../components/Toast";
import { usePersonality } from "../stores/personality";
import { useChat, type Message } from "../stores/chat";
import { sendMessage, type ChatResponse } from "../api/chat";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SURFACE_LABELS: Record<string, string> = {
  chat: "Chat",
  control: "Command",
  local: "Info",
  code: "Code",
  desktop: "Desktop",
  reason: "Reasoning",
};

const SURFACE_COLORS: Record<string, string> = {
  control: "bg-blue-500/15 text-[#5b8fd9] border-blue-500/20",
  code: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  reason: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  desktop: "bg-amber-500/15 text-amber-400 border-amber-500/20",
  local: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
};

const DEFAULT_BADGE = "bg-accent-muted text-accent border-accent/20";

/* ------------------------------------------------------------------ */
/*  Typing indicator                                                   */
/* ------------------------------------------------------------------ */

function TypingIndicator() {
  return (
    <div className="flex justify-start animate-fade-in">
      <div className="glass rounded-2xl rounded-bl-md px-5 py-3.5">
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-2 h-2 rounded-full bg-accent animate-bounce"
            style={{ animationDelay: "0ms", animationDuration: "1.2s" }}
          />
          <span
            className="inline-block w-2 h-2 rounded-full bg-accent animate-bounce"
            style={{ animationDelay: "200ms", animationDuration: "1.2s" }}
          />
          <span
            className="inline-block w-2 h-2 rounded-full bg-accent animate-bounce"
            style={{ animationDelay: "400ms", animationDuration: "1.2s" }}
          />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

function EmptyState({ assistantName }: { assistantName: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 animate-fade-in select-none">
      {/* Decorative icon */}
      <div className="relative">
        <div className="w-24 h-24 rounded-full bg-accent/10 flex items-center justify-center">
          <svg
            className="w-12 h-12 text-accent"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
            />
          </svg>
        </div>
        <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-accent animate-pulse-glow" />
      </div>

      <div className="text-center space-y-2 max-w-sm">
        <h2 className="font-display text-xl font-semibold text-text-primary">
          Talk to {assistantName}
        </h2>
        <p className="font-body text-sm text-text-secondary leading-relaxed">
          Ask anything — from daily briefings and schedule management to code
          reviews and research. {assistantName} is ready when you are.
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-2 max-w-md">
        {[
          "What's on my schedule today?",
          "Run a morning briefing",
          "Summarise my open PRs",
          "Help me plan my week",
        ].map((suggestion) => (
          <span
            key={suggestion}
            className="text-xs font-body text-text-secondary bg-surface border border-border-subtle rounded-full px-3 py-1.5 cursor-default"
          >
            {suggestion}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Surface badge                                                      */
/* ------------------------------------------------------------------ */

function SurfaceBadge({ surface }: { surface: string }) {
  const label = SURFACE_LABELS[surface] ?? surface;
  const color = SURFACE_COLORS[surface] ?? DEFAULT_BADGE;

  return (
    <span
      className={`inline-block text-[10px] font-mono font-medium uppercase tracking-widest rounded-full border px-2 py-0.5 mb-1.5 ${color}`}
    >
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Message bubble                                                     */
/* ------------------------------------------------------------------ */

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const timeStr = msg.timestamp.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-slide-up`}
    >
      <div
        className={`max-w-[78%] md:max-w-[70%] rounded-2xl px-4 py-3 transition-colors ${
          isUser
            ? "bg-accent text-void rounded-br-md shadow-lg shadow-accent/10"
            : "glass rounded-bl-md"
        }`}
      >
        {/* Surface badge for JARVIS */}
        {!isUser && msg.surface && msg.surface !== "chat" && (
          <SurfaceBadge surface={msg.surface} />
        )}

        {/* Body */}
        {isUser ? (
          <p className="text-sm font-body whitespace-pre-wrap leading-relaxed">
            {msg.text}
          </p>
        ) : (
          <div className="text-sm font-body prose prose-sm prose-invert max-w-none leading-relaxed [&_p]:my-1.5 [&_ul]:my-1.5 [&_ol]:my-1.5 [&_li]:my-0.5 [&_pre]:bg-black/30 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:my-2 [&_code]:text-accent [&_code]:font-mono [&_code]:text-xs [&_a]:text-accent [&_a]:underline [&_a]:underline-offset-2 [&_h1]:text-text-primary [&_h2]:text-text-primary [&_h3]:text-text-primary [&_strong]:text-text-primary [&_blockquote]:border-accent/40 [&_blockquote]:text-text-secondary [&_hr]:border-border-subtle">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.text}
            </ReactMarkdown>
          </div>
        )}

        {/* Timestamp */}
        <span
          className={`text-[10px] font-mono block mt-1.5 ${
            isUser ? "text-void/50" : "text-text-muted"
          }`}
        >
          {timeStr}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Send icon                                                          */
/* ------------------------------------------------------------------ */

function SendIcon() {
  return (
    <svg
      className="w-5 h-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Chat component                                                */
/* ------------------------------------------------------------------ */

export function Chat() {
  const { toast } = useToast();
  const { assistantName, userName } = usePersonality();
  const { messages, setMessages, loaded, loadHistory, clearMessages } =
    useChat();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Load history once */
  useEffect(() => {
    loadHistory(userName, assistantName);
  }, [loadHistory, userName, assistantName]);

  /* Auto-scroll on new messages or sending state change */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  /* Auto-resize textarea */
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => {
    autoResize();
  }, [input, autoResize]);

  /* Send handler */
  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const res: ChatResponse = await sendMessage(text);
      const jarvisMsg: Message = {
        id: Date.now() + 1,
        role: "jarvis",
        text: res.reply,
        surface: res.surface,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, jarvisMsg]);
    } catch {
      toast("Failed to send message", "error");
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  /* Keyboard: Enter sends, Shift+Enter newline */
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  /* Loading state */
  if (!loaded) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-5rem)]">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-accent animate-bounce" />
          <div
            className="w-2 h-2 rounded-full bg-accent animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <div
            className="w-2 h-2 rounded-full bg-accent animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] md:h-[calc(100vh-2rem)]">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between pb-4 border-b border-border-subtle mb-1">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-accent/15 flex items-center justify-center">
            <svg
              className="w-4.5 h-4.5 text-accent"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
              />
            </svg>
          </div>
          <div>
            <h1 className="font-display text-lg font-semibold text-text-primary leading-tight">
              {assistantName}
            </h1>
            <p className="text-xs font-body text-text-secondary">
              {sending ? "Typing..." : "Online"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasMessages && messages.length > 1 && (
            <button
              onClick={() => clearMessages(userName)}
              className="btn-ghost text-xs font-body flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
              title="Clear conversation"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
                />
              </svg>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ---- Messages area ---- */}
      {hasMessages ? (
        <div className="flex-1 overflow-y-auto space-y-3 py-4 scrollbar-thin scrollbar-thumb-border-default scrollbar-track-transparent">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {sending && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      ) : (
        <>
          <EmptyState assistantName={assistantName} />
          <div ref={bottomRef} />
        </>
      )}

      {/* ---- Input bar ---- */}
      <div className="pt-3 pb-1 border-t border-border-subtle">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${assistantName}...`}
            disabled={sending}
            rows={1}
            className="input-base flex-1 resize-none rounded-xl px-4 py-3 text-sm font-body leading-relaxed min-h-[48px] max-h-[160px] transition-all focus:ring-1 focus:ring-accent/30 disabled:opacity-40"
            autoFocus
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="btn-primary flex items-center justify-center w-12 h-12 rounded-xl shrink-0 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            title="Send message"
          >
            <SendIcon />
          </button>
        </div>
        <p className="text-[10px] font-body text-text-muted text-center mt-2">
          Enter to send &middot; Shift + Enter for new line
        </p>
      </div>
    </div>
  );
}
