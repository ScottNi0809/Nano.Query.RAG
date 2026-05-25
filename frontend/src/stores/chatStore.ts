import { create } from 'zustand';
import type { SourceInfo } from '@/api/chat';
import { streamChat } from '@/api/chat';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceInfo[];
  isStreaming?: boolean;
  timestamp: number;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  sendMessage: (question: string) => Promise<void>;
  clearMessages: () => void;
  newSession: () => void;
  switchSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
}

const STORAGE_KEY = 'wtg-rag-chat-sessions';
const ACTIVE_KEY = 'wtg-rag-active-session';

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

function saveActiveId(id: string | null) {
  if (id) localStorage.setItem(ACTIVE_KEY, id);
  else localStorage.removeItem(ACTIVE_KEY);
}

function deriveTitle(messages: ChatMessage[]): string {
  const first = messages.find((m) => m.role === 'user');
  if (!first) return 'New Chat';
  const text = first.content.trim();
  return text.length > 30 ? text.slice(0, 30) + '...' : text;
}

let messageCounter = 0;
const nextId = () => `msg-${Date.now()}-${++messageCounter}`;
const nextSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const initialSessions = loadSessions();
const savedActiveId = localStorage.getItem(ACTIVE_KEY);
const initialActiveId = savedActiveId && initialSessions.some((s) => s.id === savedActiveId)
  ? savedActiveId
  : null;
const initialMessages = initialActiveId
  ? initialSessions.find((s) => s.id === initialActiveId)?.messages ?? []
  : [];

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: initialSessions,
  activeSessionId: initialActiveId,
  messages: initialMessages,
  isLoading: false,

  newSession: () => {
    set({ activeSessionId: null, messages: [], isLoading: false });
    saveActiveId(null);
  },

  switchSession: (sessionId: string) => {
    const session = get().sessions.find((s) => s.id === sessionId);
    if (session) {
      set({ activeSessionId: sessionId, messages: session.messages, isLoading: false });
      saveActiveId(sessionId);
    }
  },

  deleteSession: (sessionId: string) => {
    const { sessions, activeSessionId } = get();
    const updated = sessions.filter((s) => s.id !== sessionId);
    saveSessions(updated);
    if (activeSessionId === sessionId) {
      set({ sessions: updated, activeSessionId: null, messages: [], isLoading: false });
      saveActiveId(null);
    } else {
      set({ sessions: updated });
    }
  },

  sendMessage: async (question: string) => {
    const { activeSessionId, sessions } = get();

    let sessionId = activeSessionId;
    let updatedSessions = [...sessions];

    // Create a new session if none is active
    if (!sessionId) {
      sessionId = nextSessionId();
      const newSess: ChatSession = {
        id: sessionId,
        title: question.length > 30 ? question.slice(0, 30) + '...' : question,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      updatedSessions = [newSess, ...updatedSessions];
    }

    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: question,
      timestamp: Date.now(),
    };

    const assistantId = nextId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: Date.now(),
    };

    const newMessages = [...get().messages, userMsg, assistantMsg];

    // Persist immediately
    updatedSessions = updatedSessions.map((s) =>
      s.id === sessionId
        ? { ...s, messages: newMessages, title: deriveTitle(newMessages), updatedAt: Date.now() }
        : s,
    );
    saveSessions(updatedSessions);
    saveActiveId(sessionId);

    set({
      activeSessionId: sessionId,
      sessions: updatedSessions,
      messages: newMessages,
      isLoading: true,
    });

    const persistMessages = (msgs: ChatMessage[]) => {
      const s = get().sessions.map((sess) =>
        sess.id === sessionId ? { ...sess, messages: msgs, updatedAt: Date.now() } : sess,
      );
      saveSessions(s);
      set({ sessions: s });
    };

    try {
      for await (const event of streamChat(question)) {
        if (event.type === 'token') {
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + event.data } : m,
            ),
          }));
        } else if (event.type === 'sources') {
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === assistantId ? { ...m, sources: event.sources } : m,
            ),
          }));
        } else if (event.type === 'error') {
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${event.data}`, isStreaming: false }
                : m,
            ),
          }));
        }
      }
    } catch (err) {
      const errorText = err instanceof Error ? err.message : 'Unknown error';
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === assistantId
            ? { ...m, content: m.content || `Error: ${errorText}`, isStreaming: false }
            : m,
        ),
      }));
    } finally {
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m,
        ),
      }));
      set({ isLoading: false });
      // Final persist
      persistMessages(get().messages);
    }
  },

  clearMessages: () => {
    const { activeSessionId, sessions } = get();
    if (activeSessionId) {
      const updated = sessions.filter((s) => s.id !== activeSessionId);
      saveSessions(updated);
      set({ sessions: updated, activeSessionId: null, messages: [], isLoading: false });
      saveActiveId(null);
    } else {
      set({ messages: [], isLoading: false });
    }
  },
}));
