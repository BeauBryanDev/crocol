import { create } from 'zustand';
import { VisionResult } from '../../../types/api.types';
import { useMapOverlayStore } from '../../map-overlay/store/mapOverlayStore';

// Session only: blob URLs and base64 images die with the page, like the
// overlay in the chat bubble.
interface VisionState {
  messageId: string | null;
  imageUrl: string | null;
  overlayB64: string | null;
  result: VisionResult | null;
  setResult: (messageId: string, result: VisionResult, imageUrl: string | null, overlayB64: string | null) => void;
}

export const useVisionStore = create<VisionState>()((set) => ({
  messageId: null,
  imageUrl: null,
  overlayB64: null,
  result: null,
  setResult: (messageId, result, imageUrl, overlayB64) => {
    set({ messageId, result, imageUrl, overlayB64 });
    useMapOverlayStore.getState().open('vision');
  }
}));
