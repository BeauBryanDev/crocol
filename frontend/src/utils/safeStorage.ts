import { StateStorage } from 'zustand/middleware';

// localStorage can be missing, blocked (private mode) or full: the app
// must keep working, it just stops remembering.
export const safeStorage: StateStorage = {
  getItem: (name) => {
    try {
      return window.localStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name, value) => {
    try {
      window.localStorage.setItem(name, value);
    } catch {
      // Quota exceeded or storage blocked.
    }
  },
  removeItem: (name) => {
    try {
      window.localStorage.removeItem(name);
    } catch {
      // Storage blocked.
    }
  }
};
