import { create } from 'zustand';

export type MapOverlay = 'wellsim' | 'vision';

// One results panel at a time covers the geology map.
interface MapOverlayState {
  active: MapOverlay | null;
  open: (overlay: MapOverlay) => void;
  close: () => void;
}

export const useMapOverlayStore = create<MapOverlayState>()((set) => ({
  active: null,
  open: (active) => set({ active }),
  close: () => set({ active: null })
}));
