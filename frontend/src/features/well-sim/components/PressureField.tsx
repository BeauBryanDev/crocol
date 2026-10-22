import React, { useMemo } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useLanguage } from '../../../i18n/useLanguage';
import { WellRunResponse } from '../../../types/api.types';

// Warm sequential palette: small drawdown deep green, largest amber.
const PALETTE = ['#1f4d24', '#2F7D32', '#7cb342', '#c0ca33', '#fdd835', '#ffb300'];
const LEGEND_QUANTILES = [0, 0.25, 0.5, 0.75, 1];
const WIDTH = 300;
const HEIGHT = 110;
const tooltipStyle = { backgroundColor: '#24180F', borderColor: '#F2E8D5', borderRadius: '6px', fontSize: '10px', color: '#F2E8D5' };

const mix = (a: string, b: string, f: number): string => {
  const ca = parseInt(a.slice(1), 16);
  const cb = parseInt(b.slice(1), 16);
  const channel = (shift: number) => Math.round(((ca >> shift) & 255) * (1 - f) + ((cb >> shift) & 255) * f);
  return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
};

const paletteAt = (share: number): string => {
  const x = Math.min(Math.max(share, 0), 1) * (PALETTE.length - 1);
  const i = Math.min(Math.floor(x), PALETTE.length - 2);
  return mix(PALETTE[i], PALETTE[i + 1], x - i);
};

// Rank of a value among all cells (ties share their mean rank), in [0, 1].
// Equalizing by rank spreads the palette over every part of the ΔP range,
// so small changes far from the well stay visible next to the steep
// near-well drop.
const ranker = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const bound = (v: number, upper: boolean) => {
    let lo = 0;
    let hi = n;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid] < v || (upper && sorted[mid] === v)) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  };
  const share = (v: number) => (n < 2 ? 0.5 : ((bound(v, false) + bound(v, true) - 1) / 2) / (n - 1));
  const quantile = (q: number) => sorted[Math.min(n - 1, Math.round(q * (n - 1)))];
  return { share, quantile, min: sorted[0], max: sorted[n - 1] };
};

const psi = (v: number, span: number): string =>
  v.toLocaleString(undefined, { maximumFractionDigits: span < 10 ? 2 : span < 100 ? 1 : 0 });

// Cell edges sit halfway between cell centres in log(r), as on the solver's
// logarithmic grid; depth increases downwards.
export const PressureField: React.FC<{ run: WellRunResponse }> = ({ run }) => {
  const { t } = useLanguage();
  const { r_cell_ft: r, z_cell_ft: z, pressure_drop_final_psi: drop } = run.fields;

  const model = useMemo(() => {
    if (!r.length || !z.length) return null;
    const logs = r.map((v) => Math.log(v));
    const half = logs.length > 1 ? (logs[1] - logs[0]) / 2 : 0.5;
    const edges = [logs[0] - half, ...logs.slice(1).map((v, i) => (v + logs[i]) / 2), logs[logs.length - 1] + half];
    const span = edges[edges.length - 1] - edges[0];
    const xOf = (v: number) => ((v - edges[0]) / span) * WIDTH;
    const mid = Math.floor(z.length / 2);
    const profile = r.map((radius, i) => ({ r: radius, dp: drop[i][mid] }));
    return { edges, xOf, rank: ranker(drop.flat()), profile, midZ: z[mid] };
  }, [r, z, drop]);

  if (!model) return null;
  const { edges, xOf, rank, profile, midZ } = model;
  const rowH = HEIGHT / z.length;
  const range = rank.max - rank.min;
  const gradient = `linear-gradient(to right, ${PALETTE.join(', ')})`;

  return (
    <div className="space-y-1">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-[110px] rounded-xs border border-[#F2E8D5]/20"
        preserveAspectRatio="none" role="img" aria-label={t.wsField}>
        {drop.map((column, i) =>
          column.map((value, k) => (
            <rect key={`${i}-${k}`} x={xOf(edges[i])} y={k * rowH} width={Math.max(xOf(edges[i + 1]) - xOf(edges[i]), 0.5)}
              height={rowH} fill={paletteAt(rank.share(value))}>
              <title>{`r ${r[i].toPrecision(3)} ft · z ${z[k].toPrecision(3)} ft · ΔP ${psi(value, range)} psi`}</title>
            </rect>
          ))
        )}
      </svg>
      <div className="flex justify-between text-[9px] text-[#F2E8D5]/60">
        <span>r {r[0].toPrecision(3)} ft</span>
        <span>r {Math.round(r[r.length - 1]).toLocaleString()} ft</span>
      </div>

      <div className="h-2 rounded-xs" style={{ background: gradient }} />
      <div className="flex justify-between text-[9px] text-[#F2E8D5]/70">
        {LEGEND_QUANTILES.map((q) => (
          <span key={q}>{psi(rank.quantile(q), range)}</span>
        ))}
      </div>
      <p className="text-[9px] text-[#F2E8D5]/55">{t.wsFieldLegend}</p>

      <h4 className="text-[10px] font-semibold text-[#D9B36C] pt-1">
        {t.wsProfile} (z ≈ {midZ.toPrecision(3)} ft)
      </h4>
      <div className="h-[120px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={profile} margin={{ top: 6, right: 8, left: -6, bottom: 0 }}>
            <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
            <XAxis dataKey="r" type="number" scale="log" domain={['dataMin', 'dataMax']} allowDataOverflow
              tick={{ fill: '#D9B36C', fontSize: 9 }} tickFormatter={(v: number) => (v < 10 ? v.toPrecision(2) : `${Math.round(v)}`)} />
            <YAxis tick={{ fill: '#c0ca33', fontSize: 9 }} width={44} domain={['auto', 'auto']}
              tickFormatter={(v: number) => psi(v, range)} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => `r = ${Number(v).toPrecision(3)} ft`}
              formatter={(v) => [`${psi(Number(v), range)} psi`, 'ΔP']} />
            <Line type="monotone" dataKey="dp" stroke="#fdd835" strokeWidth={2} dot={{ r: 1.5, fill: '#c0ca33' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
