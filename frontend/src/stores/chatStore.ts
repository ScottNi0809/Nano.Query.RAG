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

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  sendMessage: (question: string) => Promise<void>;
  clearMessages: () => void;
}

let messageCounter = 0;
const nextId = () => `msg-${Date.now()}-${++messageCounter}`;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,

  sendMessage: async (question: string) => {
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

    set((state) => ({
      messages: [...state.messages, userMsg, assistantMsg],
      isLoading: true,
    }));

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
        isLoading: get().messages.some((m) => m.id === assistantId && m.isStreaming) ? false : false,
      }));
      set({ isLoading: false });
    }
  },

  clearMessages: () => set({ messages: [], isLoading: false }),
}));
