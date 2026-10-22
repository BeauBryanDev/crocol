import React from 'react';
import { Gauge, X } from 'lucide-react';
import { useLanguage } from '../../../i18n/useLanguage';
import { WellCase, WellRunResponse, WellSweepResponse } from '../../../types/api.types';
import { useWellSimStore } from '../store/wellSimStore';
import { useMapOverlayStore } from '../../map-overlay/store/mapOverlayStore';
import { fmt, rowsOf, SweepChart, Tile } from './ResultParts';
import { PressureField } from './PressureField';

type Strings = ReturnType<typeof useLanguage>['t'];

const caseLine = (label: string, row: WellCase | null, unit: string) =>
  row ? `${label}: ${fmt(row.target, 1)} ${unit} · Np ${fmt(row.np_stb)} STB · ${fmt(row.rf * 100, 2)} %` : null;

const RunView: React.FC<{ run: WellRunResponse; t: Strings }> = ({ run, t }) => {
  const s = run.summary;
  return (
    <section className="space-y-1.5">
      <h3 className="text-[11px] font-bold text-[#F2E8D5]">{t.wsRunSummary}</h3>
      <div className="grid grid-cols-3 gap-1">
        <Tile label={t.wsNp} value={`${fmt(s.np_stb)} STB`} />
        <Tile label={t.wsRf} value={`${fmt(s.recovery_factor * 100, 2)} %`} />
        <Tile label={t.wsPlateau} value={s.plateau_days === null ? '—' : `${fmt(s.plateau_days)} ${t.wsDays}`} />
        <Tile label={t.wsQFinal} value={`${fmt(s.q_final_stb_d, 1)} STB/d`} />
        <Tile label={t.wsPwfFinal} value={`${fmt(s.pwf_final_psi)} psi`} />
        <Tile label={t.wsEndedBy} value={s.ended_by === 'abandonment' ? t.wsEndedAbandon : t.wsEndedHorizon} />
      </div>
      <Tile label={`${t.wsPwfFloor} (${s.floor_source})`} value={`${fmt(s.pwf_floor_psi)} psi · ${s.valid ? t.wsValid : t.wsInvalid}`}
        tone={s.valid ? 'ok' : 'bad'} />
      {run.warnings.length > 0 && (
        <ul className="text-[9.5px] text-[#e57373] list-disc pl-4">
          {run.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
      <h4 className="text-[10px] font-semibold text-[#D9B36C] pt-1">{t.wsField}</h4>
      <PressureField run={run} />
      <p className="text-[9px] text-[#F2E8D5]/55">{t.wsFieldAxis}</p>
    </section>
  );
};

const SweepView: React.FC<{ sweep: WellSweepResponse; t: Strings }> = ({ sweep, t }) => {
  const lines = [
    caseLine(t.wsRecommended, sweep.recommended_rate, 'STB/d'),
    caseLine(t.wsBestDiscounted, sweep.best_discounted_rate, 'STB/d'),
    caseLine(t.wsBestBhp, sweep.best_bhp, 'psi')
  ].filter(Boolean);
  const rows = rowsOf(sweep);

  return (
    <section className="space-y-1.5">
      <h3 className="text-[11px] font-bold text-[#F2E8D5]">{t.wsSweepSummary}</h3>
      <ul className="text-[10px] text-[#F2E8D5]/90 space-y-0.5">
        {lines.map((line) => <li key={line}>{line}</li>)}
      </ul>
      <h4 className="text-[10px] font-semibold text-[#D9B36C]">{t.wsChartNpVsRate}</h4>
      <SweepChart sweep={sweep} />
      <div className="max-h-[150px] overflow-auto border border-[#F2E8D5]/20 rounded-xs">
        <table className="w-full text-[9.5px] text-[#F2E8D5]/90">
          <thead className="sticky top-0 bg-[#18100a] text-[#D9B36C]">
            <tr>
              <th className="px-1 text-left">{t.wsControl}</th>
              <th className="px-1 text-right">{t.wsTarget}</th>
              <th className="px-1 text-right">Np</th>
              <th className="px-1 text-right">RF %</th>
              <th className="px-1 text-left">{t.wsLimit}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.control}-${r.target}`} className={r.valid ? '' : 'text-[#e57373]'}>
                <td className="px-1">{r.control}</td>
                <td className="px-1 text-right">{fmt(r.target, 1)}</td>
                <td className="px-1 text-right">{fmt(r.np_stb)}</td>
                <td className="px-1 text-right">{fmt(r.rf * 100, 2)}</td>
                <td className="px-1 truncate max-w-[90px]">{r.limit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sweep.notes.length > 0 && (
        <details className="text-[9.5px] text-[#F2E8D5]/75">
          <summary className="cursor-pointer text-[#D9B36C]">{t.wsNotes}</summary>
          <ul className="list-disc pl-4 space-y-0.5 mt-0.5">
            {sweep.notes.map((note) => <li key={note}>{note}</li>)}
          </ul>
        </details>
      )}
    </section>
  );
};

export const WellSimResults: React.FC = () => {
  const { t } = useLanguage();
  const { run, sweep } = useWellSimStore();
  const close = useMapOverlayStore((state) => state.close);

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#24180F]/97 border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-2xl">
      <div className="shrink-0 mb-1.5 pb-1.5 border-b border-[#F2E8D5]/30 flex items-center gap-1.5">
        <Gauge className="w-4 h-4 text-[#D9B36C] shrink-0" />
        <h2 className="flex-1 text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">{t.wsResultsTitle}</h2>
        <button type="button" onClick={close} title={t.close} aria-label={t.close}
          className="p-1 rounded-xs text-[#D9B36C] hover:text-[#F2E8D5]">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-3">
        {!run && !sweep && <p className="text-[11px] text-[#F2E8D5]/80">{t.wsResultsEmpty}</p>}
        {sweep && <SweepView sweep={sweep} t={t} />}
        {run && <RunView run={run} t={t} />}
      </div>
      <p className="shrink-0 pt-1.5 mt-1 border-t border-[#F2E8D5]/20 text-[9px] text-[#F2E8D5]/55">{t.prodSimNote}</p>
    </div>
  );
};
