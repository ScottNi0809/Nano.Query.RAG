import { create } from 'zustand';

type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
  toggle: () => void;
  setMode: (mode: ThemeMode) => void;
}

const getInitialMode = (): ThemeMode => {
  const saved = localStorage.getItem('wtg-rag-theme');
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const applyThemeToDOM = (mode: ThemeMode) => {
  const root = document.documentElement;
  root.classList.remove('light', 'dark');
  root.classList.add(mode);
  root.style.colorScheme = mode;
};

// Apply initial theme immediately to avoid flash
applyThemeToDOM(getInitialMode());

export const useThemeStore = create<ThemeState>((set) => ({
  mode: getInitialMode(),
  toggle: () =>
    set((state) => {
      const next = state.mode === 'light' ? 'dark' : 'light';
      localStorage.setItem('wtg-rag-theme', next);
      applyThemeToDOM(next);
      return { mode: next };
    }),
  setMode: (mode) => {
    localStorage.setItem('wtg-rag-theme', mode);
    applyThemeToDOM(mode);
    set({ mode });
  },
}));
