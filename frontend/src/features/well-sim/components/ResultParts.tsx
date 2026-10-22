import React from 'react';
import { CartesianGrid, 
  Line, 
  LineChart, 
  ReferenceLine, 
  ResponsiveContainer, 
  Tooltip, 
  XAxis, YAxis } from 'recharts';
import { useLanguage } from '../../../i18n/useLanguage';
import { WellCase, WellSweepResponse } from '../../../types/api.types';

const NP_COLOR = '#66bb6a';
const REC_COLOR = '#F2E8D5';
const DISC_COLOR = '#D9B36C';
const tooltipStyle = { backgroundColor: '#24180F', borderColor: '#F2E8D5', borderRadius: '6px', fontSize: '10px', color: '#F2E8D5' };

export const fmt = (value: number | null | undefined, digits = 0): string =>
  value === null || value === undefined || !Number.isFinite(value)
    ? '—'
    : value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const rowsOf = (sweep: WellSweepResponse): WellCase[] =>
  sweep.rows.map((row) => Object.fromEntries(sweep.columns.map((col, i) => [col, row[i]])) as unknown as WellCase);

export const Tile: React.FC<{ label: string; value: string; tone?: 'ok' | 'bad' }> = ({ label, value, tone }) => (
  <div className="rounded-xs border border-[#F2E8D5]/25 px-1.5 py-1">
    <p className="text-[9px] text-[#D9B36C]/80 truncate">{label}</p>
    <p className={`text-[11.5px] font-bold ${tone === 'bad' ? 'text-[#e57373]' : tone === 'ok' ? 'text-[#66bb6a]' : 'text-[#F2E8D5]'}`}>
      {value}
    </p>
  </div>
);

export const SweepChart: React.FC<{ sweep: WellSweepResponse }> = ({ sweep }) => {
  const { t } = useLanguage();
  const rates = rowsOf(sweep)
    .filter((r) => r.control === 'rate' && r.valid)
    .sort((a, b) => a.target - b.target);
  if (rates.length < 2) return null;
  const rec = sweep.recommended_rate?.target;
  const disc = sweep.best_discounted_rate?.target;

  return (
    <div className="h-[150px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rates} margin={{ top: 6, right: 8, left: -6, bottom: 0 }}>
          <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
          <XAxis dataKey="target" type="number" domain={['dataMin', 'dataMax']} tick={{ fill: '#D9B36C', fontSize: 9 }}
            tickFormatter={(v: number) => fmt(v)} axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }} />
          <YAxis dataKey="np_stb" tick={{ fill: NP_COLOR, fontSize: 9 }} width={46} domain={['auto', 'auto']}
            tickFormatter={(v: number) => (v >= 1000 ? `${fmt(v / 1000, 0)}k` : fmt(v))} />
          <Tooltip contentStyle={tooltipStyle}
            labelFormatter={(v) => `${t.wsTarget}: ${fmt(Number(v), 1)} STB/d`}
            formatter={(v) => [`${fmt(Number(v))} STB`, 'Np']} />
          {rec !== undefined && <ReferenceLine x={rec} stroke={REC_COLOR} strokeDasharray="4 2" />}
          {disc !== undefined && disc !== rec && <ReferenceLine x={disc} stroke={DISC_COLOR} strokeDasharray="2 2" />}
          <Line type="monotone" dataKey="np_stb" stroke={NP_COLOR} strokeWidth={2} dot={{ r: 2, fill: NP_COLOR }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
