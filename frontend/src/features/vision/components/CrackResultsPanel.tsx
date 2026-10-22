import React from 'react';
import { ScanSearch, X } from 'lucide-react';
import { useLanguage } from '../../../i18n/useLanguage';
import { CrackSeverity } from '../../../types/api.types';
import { useMapOverlayStore } from '../../map-overlay/store/mapOverlayStore';
import { fmt, Tile } from '../../well-sim/components/ResultParts';
import { useVisionStore } from '../store/visionStore';
import { CrackViewer } from './CrackViewer';
import { RoseDiagram } from './RoseDiagram';

const SEVERITY_COLOR: Record<CrackSeverity, string> = {
  low: '#66bb6a',
  moderate: '#fdd835',
  high: '#ffb300',
  critical: '#e57373'
};

export const CrackResultsPanel: React.FC = () => {
  const { t } = useLanguage();
  const { result, imageUrl, overlayB64, messageId } = useVisionStore();
  const close = useMapOverlayStore((state) => state.close);
  if (!result) return null;
  const r = result.report;
  const ai = result.interpretation;
  const severityText = {
    low: t.cvSeverityLow,
    moderate: t.cvSeverityModerate,
    high: t.cvSeverityHigh,
    critical: t.cvSeverityCritical
  }[r.severity];

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#24180F]/97 border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-2xl">
      <div className="shrink-0 mb-1.5 pb-1.5 border-b border-[#F2E8D5]/30 flex items-center gap-1.5">
        <ScanSearch className="w-4 h-4 text-[#D9B36C] shrink-0" />
        <h2 className="flex-1 text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">{t.cvTitle}</h2>
        <span className="text-[9px] text-[#F2E8D5]/55 truncate">{r.model}</span>
        <button type="button" onClick={close} title={t.close} aria-label={t.close}
          className="p-1 rounded-xs text-[#D9B36C] hover:text-[#F2E8D5]">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2.5">
        <CrackViewer key={messageId ?? ''} imageUrl={imageUrl} maskB64={result.mask_webp_b64} overlayB64={overlayB64}
          width={r.width_px} height={r.height_px} />

        <div className="grid grid-cols-3 gap-1">
          <Tile label={t.cvDensity} value={`${fmt(r.density_pct, 2)} %`} />
          <Tile label={t.cvFractal} value={`${fmt(r.fractal_dimension, 3)} (R² ${fmt(r.fractal_r2, 2)})`} />
          <Tile label={t.cvCount} value={fmt(r.crack_count)} />
          <Tile label={t.cvLength} value={`${fmt(r.total_length_px)} px`} />
          <Tile label={t.cvMeanWidth} value={`${fmt(r.mean_width_px, 1)} px`} />
          <Tile label={t.cvMaxWidth} value={`${fmt(r.max_width_px, 1)} px`} />
          <div className="rounded-xs border px-1.5 py-1" style={{ borderColor: `${SEVERITY_COLOR[r.severity]}99` }}>
            <p className="text-[9px] text-[#D9B36C]/80">{t.cvSeverity}</p>
            <p className="text-[11.5px] font-bold" style={{ color: SEVERITY_COLOR[r.severity] }}>{severityText}</p>
          </div>
          <Tile label={t.cvConfidence} value={fmt(r.mean_confidence, 2)} />
          <Tile label={t.cvAmbiguous} value={`${fmt(r.ambiguous_pct, 1)} %`} />
        </div>
        <p className="text-[9.5px] text-[#F2E8D5]/60">
          {t.cvRun}: {r.tiles} · {fmt(r.elapsed_ms)} ms · {r.width_px}×{r.height_px} px
        </p>

        <section>
          <h3 className="text-[10.5px] font-semibold text-[#D9B36C] mb-1">{t.cvRose}</h3>
          <div className="flex items-center gap-3">
            <RoseDiagram rose={r.rose} label={t.cvRose} />
            <div className="text-[10px] text-[#F2E8D5]/90">
              <p className="font-semibold text-[#D9B36C] mb-0.5">{t.cvDominant}</p>
              {r.dominant_angles.length ? (
                <ul className="space-y-0.5">
                  {r.dominant_angles.map(([angle, share]) => (
                    <li key={angle}>{fmt(angle, 0)}° · {fmt(share * 100, 0)} %</li>
                  ))}
                </ul>
              ) : (
                <p>{t.cvNoDominant}</p>
              )}
            </div>
          </div>
        </section>

        {ai && (
          <details className="text-[10px] text-[#F2E8D5]/85 border border-[#F2E8D5]/20 rounded-xs px-2 py-1">
            <summary className="cursor-pointer text-[#D9B36C] font-semibold">{t.cvInterpretation}</summary>
            <p className="mt-1 text-[9.5px] italic text-[#D9B36C]/80">{t.cvInterpretationNote}</p>
            {!ai.is_rock && <p className="mt-1 text-[#e57373]">{t.cvNotRock}</p>}
            <dl className="mt-1 space-y-1">
              <dt className="font-semibold text-[#D9B36C]">{t.cvRock}</dt>
              <dd>{ai.rock_description}</dd>
              <dt className="font-semibold text-[#D9B36C]">{t.cvDiagnosis}</dt>
              <dd>{ai.diagnosis}</dd>
              <dt className="font-semibold text-[#D9B36C]">{t.cvFluidFlow}</dt>
              <dd>{ai.fluid_flow}</dd>
              <dt className="font-semibold text-[#D9B36C]">{t.cvAiConfidence}</dt>
              <dd>{ai.confidence}</dd>
            </dl>
          </details>
        )}
      </div>
      <p className="shrink-0 pt-1.5 mt-1 border-t border-[#F2E8D5]/20 text-[9px] text-[#F2E8D5]/55">{t.cvNote}</p>
    </div>
  );
};
