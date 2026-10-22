import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { ChatMessage } from '../../../types/chat.types';
import { safeStorage } from '../../../utils/safeStorage';

const STORAGE_KEY = 'crocol-chat';
const STORAGE_VERSION = 1;
const MAX_STORED_MESSAGES = 60;

// Blob URLs die with the page and overlays are ~55 KB of base64 each, so
// only a flag that they existed is kept.
const forStorage = (message: ChatMessage): ChatMessage => {
  const { imageUrl, overlayWebpB64, pending, ...rest } = message;
  return {
    ...rest,
    hadImage: message.hadImage || Boolean(imageUrl),
    hadOverlay: message.hadOverlay || Boolean(overlayWebpB64)
  };
};

interface ChatState {
  messages: ChatMessage[];
  addMessages: (...messages: ChatMessage[]) => void;
  updateMessage: (id: string, patch: (message: ChatMessage) => ChatMessage) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      addMessages: (...messages) => set((state) => ({ messages: [...state.messages, ...messages] })),
      updateMessage: (id, patch) =>
        set((state) => ({ messages: state.messages.map((m) => (m.id === id ? patch(m) : m)) })),
      clearMessages: () => set({ messages: [] })
    }),
    {
      name: STORAGE_KEY,
      version: STORAGE_VERSION,
      storage: createJSONStorage(() => safeStorage),
      partialize: (state) => ({
        messages: state.messages
          .filter((m) => !m.pending)
          .slice(-MAX_STORED_MESSAGES)
          .map(forStorage)
      })
    }
  )
);
