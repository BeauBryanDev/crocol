import React from 'react';
import { CartesianGrid, Legend, 
  Line, LineChart, 
  ReferenceLine, ResponsiveContainer,
   Tooltip, XAxis, YAxis } from 'recharts';
import { useLanguage } from '../../../i18n/useLanguage';
import { WellRunResponse } from '../../../types/api.types';

const Q_COLOR = '#66bb6a';
const NP_COLOR = '#8fb8de';
const PWF_COLOR = '#e57373';
const PAVG_COLOR = '#D9B36C';
const PB_COLOR = '#F2E8D5';
const tooltipStyle = { backgroundColor: '#24180F', borderColor: '#F2E8D5', borderRadius: '6px', fontSize: '10px', color: '#F2E8D5' };
const axisTick = { fill: '#D9B36C', fontSize: 9 };

const short = (v: number): string => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : `${Math.round(v)}`);
const days = (v: number): string => (v < 1 ? v.toPrecision(1) : `${Math.round(v)}`);

// Geometric time steps cluster near t = 0, so time is on a log axis.
export const SimulationCharts: React.FC<{ run: WellRunResponse }> = ({ run }) => {
  const { t } = useLanguage();
  const s = run.series;
  const data = s.t_days
    .map((time, i) => ({ t: time, q: s.q_stb_d[i], np: s.np_stb[i], pwf: s.pwf_psi[i], pavg: s.p_avg_psi[i] }))
    .filter((p) => p.t > 0);
  const pb = Number(run.inputs.pb);
  const xAxis = (
    <XAxis dataKey="t" type="number" scale="log" domain={['dataMin', 'dataMax']} tick={axisTick} tickFormatter={days}
      axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }} allowDataOverflow />
  );
  const tooltip = (
    <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => `t = ${Number(v).toPrecision(3)} ${t.wsDays}`}
      formatter={(v, name) => [Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 }), name]} />
  );

  return (
    <div className="flex-1 min-h-0 flex flex-col gap-1">
      <div className="flex-1 min-h-[110px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 2, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
            {xAxis}
            <YAxis yAxisId="q" tick={{ fill: Q_COLOR, fontSize: 9 }} width={42} tickFormatter={short} />
            <YAxis yAxisId="np" orientation="right" tick={{ fill: NP_COLOR, fontSize: 9 }} width={42} tickFormatter={short} />
            {tooltip}
            <Legend wrapperStyle={{ fontSize: 9.5, color: '#F2E8D5' }} iconSize={8} />
            <Line yAxisId="q" type="stepAfter" dataKey="q" name="q (STB/d)" stroke={Q_COLOR} strokeWidth={2} dot={false} />
            <Line yAxisId="np" type="monotone" dataKey="np" name="Np (STB)" stroke={NP_COLOR} strokeWidth={1.8} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex-1 min-h-[110px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 12, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
            {xAxis}
            <YAxis tick={axisTick} width={42} tickFormatter={short}
              domain={[(min: number) => Math.min(min, Number.isFinite(pb) ? pb : min) * 0.97, 'auto']} />
            {tooltip}
            <Legend wrapperStyle={{ fontSize: 9.5, color: '#F2E8D5' }} iconSize={8} />
            {Number.isFinite(pb) && (
              <ReferenceLine y={pb} stroke={PB_COLOR} strokeDasharray="4 3"
                label={{ value: `pb ${short(pb)}`, fill: PB_COLOR, fontSize: 9, position: 'insideBottomRight' }} />
            )}
            <Line type="monotone" dataKey="pwf" name="pwf (psi)" stroke={PWF_COLOR} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="pavg" name="p̄ (psi)" stroke={PAVG_COLOR} strokeWidth={1.8} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[9px] text-[#F2E8D5]/55 text-center">{t.prodSimTime}</p>
    </div>
  );
};
