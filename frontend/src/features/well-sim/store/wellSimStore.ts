import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { WellRunResponse, WellSweepResponse } from '../../../types/api.types';
import { safeStorage } from '../../../utils/safeStorage';
import { useMapOverlayStore } from '../../map-overlay/store/mapOverlayStore';
import { Choices, SectionId } from '../fields';

const STORAGE_KEY = 'crocol-wellsim';
const STORAGE_VERSION = 1;

interface WellSimState {
  values: Record<string, string>;
  choices: Choices | null;
  openSections: Partial<Record<SectionId, boolean>>;
  formOpen: boolean;
  run: WellRunResponse | null;
  runAt: number;
  sweep: WellSweepResponse | null;
  setForm: (values: Record<string, string>, choices: Choices) => void;
  setValue: (key: string, value: string) => void;
  setChoice: <K extends keyof Choices>(key: K, value: Choices[K]) => void;
  toggleSection: (id: SectionId, open: boolean) => void;
  setFormOpen: (open: boolean) => void;
  setRun: (run: WellRunResponse) => void;
  setSweep: (sweep: WellSweepResponse) => void;
}

// Only the user's inputs are remembered; results are recomputed on demand.
export const useWellSimStore = create<WellSimState>()(
  persist(
    (set) => ({
      values: {},
      choices: null,
      openSections: {},
      formOpen: false,
      run: null,
      runAt: 0,
      sweep: null,
      setForm: (values, choices) => set({ values, choices }),
      setValue: (key, value) => set((state) => ({ values: { ...state.values, [key]: value } })),
      setChoice: (key, value) =>
        set((state) => (state.choices ? { choices: { ...state.choices, [key]: value } } : {})),
      toggleSection: (id, open) => set((state) => ({ openSections: { ...state.openSections, [id]: open } })),
      setFormOpen: (formOpen) => set({ formOpen }),
      setRun: (run) => {
        set({ run, runAt: Date.now() });
        useMapOverlayStore.getState().open('wellsim');
      },
      setSweep: (sweep) => {
        set({ sweep });
        useMapOverlayStore.getState().open('wellsim');
      }
    }),
    {
      name: STORAGE_KEY,
      version: STORAGE_VERSION,
      storage: createJSONStorage(() => safeStorage),
      partialize: (state) => ({ values: state.values, choices: state.choices, openSections: state.openSections })
    }
  )
);
