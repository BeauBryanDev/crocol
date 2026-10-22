import React, { useState } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';

type Mode = 'photo' | 'mask' | 'overlay';

interface CrackViewerProps {
  imageUrl: string | null;
  maskB64: string | null;
  overlayB64: string | null;
  width: number;
  height: number;
}

const DEFAULT_OPACITY = 70;
const layer = 'absolute inset-0 w-full h-full object-contain';

// The mask is rendered at the overlay's size and aspect, so it lines up with
// the photo when both fill the same box with object-contain.
export const CrackViewer: React.FC<CrackViewerProps> = ({ imageUrl, maskB64, overlayB64, width, height }) => {
  const { t } = useLanguage();
  const canStack = Boolean(imageUrl && maskB64);
  const [mode, setMode] = useState<Mode>(canStack ? 'mask' : 'overlay');
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);

  const modes: { value: Mode; label: string; enabled: boolean }[] = [
    { value: 'photo', label: t.cvPhoto, enabled: Boolean(imageUrl) },
    { value: 'mask', label: t.cvMask, enabled: canStack },
    { value: 'overlay', label: t.cvOverlay, enabled: Boolean(overlayB64) }
  ];

  return (
    <div className="space-y-1.5">
      <div className="relative w-full max-h-[260px] rounded-xs border border-[#F2E8D5]/25 bg-[#18100a] overflow-hidden"
        style={{ aspectRatio: `${width} / ${height}` }}>
        {mode === 'overlay' && overlayB64 ? (
          <img src={`data:image/webp;base64,${overlayB64}`} alt={t.overlayTitle} className={layer} />
        ) : (
          <>
            {imageUrl && <img src={imageUrl} alt={t.cvPhoto} className={layer} />}
            {mode === 'mask' && maskB64 && (
              <img src={`data:image/webp;base64,${maskB64}`} alt={t.cvMask} className={layer}
                style={{ opacity: opacity / 100 }} />
            )}
          </>
        )}
      </div>
      {!imageUrl && <p className="text-[9.5px] text-[#D9B36C]/70 italic">{t.cvNoPhoto}</p>}

      <div className="flex items-center gap-2">
        <div className="flex rounded-xs border border-[#F2E8D5]/35 overflow-hidden" role="radiogroup" aria-label={t.cvTitle}>
          {modes.map((m) => (
            <button key={m.value} type="button" role="radio" aria-checked={mode === m.value} disabled={!m.enabled}
              onClick={() => setMode(m.value)}
              className={`px-2 py-0.5 text-[10px] font-semibold disabled:opacity-35 ${
                mode === m.value ? 'bg-[#2F7D32] text-[#F2E8D5]' : 'text-[#D9B36C] hover:bg-[#F2E8D5]/10'
              }`}>
              {m.label}
            </button>
          ))}
        </div>
        {mode === 'mask' && (
          <label className="flex-1 flex items-center gap-1.5 text-[9.5px] text-[#F2E8D5]/80">
            <span className="shrink-0">{t.cvOpacity}</span>
            <input type="range" min={0} max={100} step={5} value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))} className="flex-1 accent-[#e53935]" />
            <span className="w-8 text-right">{opacity} %</span>
          </label>
        )}
      </div>
    </div>
  );
};
