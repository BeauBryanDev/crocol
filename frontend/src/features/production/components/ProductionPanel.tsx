import React, { useEffect, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { TrendingUp, TrendingDown, Minus, Activity, MessageSquareText } from 'lucide-react';
import { useLanguage } from '../../../i18n/useLanguage';
import { translations } from '../../../i18n/translations';
import { useChatStore } from '../../chat/store/chatStore';
import { ProductionSeries, ProductionTrend } from '../../../types/api.types';
import { ChatMessage } from '../../../types/chat.types';
import { useWellSimStore } from '../../well-sim/store/wellSimStore';
import { SimulationCharts } from './SimulationCharts';

type Strings = (typeof translations)['en'];

const OIL_COLOR = '#66bb6a';
const GAS_COLOR = '#d9b36c';

// The series always come from Crocol's latest answer: users ask the agent,
// they never pick a field here.
const useLatestProduction = (): ProductionSeries[] =>
  useChatStore((state) => {
    for (let i = state.messages.length - 1; i >= 0; i -= 1) {
      const series = state.messages[i].production;
      if (series && series.length) return series;
    }
    return EMPTY;
  });
const EMPTY: ProductionSeries[] = [];

// Answer ids are `a-<Date.now()>` (ChatPanel), which orders them against a
// simulation run's timestamp.
const stampOf = (message: ChatMessage): number => Number(message.id.slice(2)) || 0;

const useLatestProductionAt = (): number =>
  useChatStore((state) => {
    for (let i = state.messages.length - 1; i >= 0; i -= 1) {
      if (state.messages[i].production?.length) return stampOf(state.messages[i]);
    }
    return 0;
  });

type Source = 'anh' | 'sim';

const trendText = (trend: ProductionTrend, t: Strings): string =>
  ({
    decreasing: t.trendDecreasing,
    increasing: t.trendIncreasing,
    stable: t.trendStable,
    variable: t.trendVariable,
    no_production: t.trendNone,
    insufficient_data: t.trendInsufficient
  })[trend.label];

const TrendBadge: React.FC<{ label: string; trend: ProductionTrend; color: string; t: Strings }> = ({
  label,
  trend,
  color,
  t
}) => {
  const Icon = trend.label === 'decreasing' ? TrendingDown : trend.label === 'increasing' ? TrendingUp : trend.label === 'variable' ? Activity : Minus;
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border text-[9.5px]"
      style={{ borderColor: `${color}99`, color }}
      title={trend.change_pct !== null ? `${trend.change_pct.toFixed(1)} % ${t.prodChange}` : undefined}
    >
      <Icon className="w-3 h-3" />
      <span className="font-semibold">{label}:</span>
      <span>{trendText(trend, t)}</span>
      {trend.change_pct !== null && <span className="opacity-80">({trend.change_pct > 0 ? '+' : ''}{trend.change_pct.toFixed(1)} %)</span>}
    </span>
  );
};

const monthLabel = (iso: string, language: string): string =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(language === 'es' ? 'es-CO' : 'en-US', { month: 'short', year: '2-digit' });

const SeriesChart: React.FC<{ series: ProductionSeries; compact: boolean }> = ({ series, compact }) => {
  const { language, t } = useLanguage();
  const data = series.points.map((p) => ({ ...p, label: monthLabel(p.month, language) }));
  const hasGas = series.points.some((p) => p.gas !== null && p.gas > 0);
  const place = [series.municipalities.join(', '), series.departments.join(', ')].filter(Boolean).join(' · ');

  return (
    <section className={`flex flex-col ${compact ? 'min-h-[190px]' : 'flex-1 min-h-[170px]'}`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="min-w-0">
          <h3 className="text-[11.5px] font-bold text-[#F2E8D5] truncate">
            {series.name}
            {series.kind === 'contract' && (
              <span className="ml-1 font-normal text-[#D9B36C]/70">({series.fields.join(' + ')})</span>
            )}
          </h3>
          <p className="text-[9.5px] text-[#D9B36C]/75 truncate">
            {series.operators.join(', ')}
            {place && ` · ${place}`}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-1">
        <TrendBadge label={t.prodOil} trend={series.trends.oil} color={OIL_COLOR} t={t} />
        {hasGas && <TrendBadge label={t.prodGas} trend={series.trends.gas} color={GAS_COLOR} t={t} />}
      </div>
      <div className="flex-1 min-h-[120px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: hasGas ? 4 : 12, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: '#D9B36C', fontSize: 9 }} interval="preserveStartEnd" minTickGap={18}
              axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }} tickLine={{ stroke: '#F2E8D5', opacity: 0.3 }} />
            <YAxis yAxisId="oil" tick={{ fill: OIL_COLOR, fontSize: 9 }} width={44} domain={['auto', 'auto']}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`)}
              axisLine={{ stroke: OIL_COLOR, opacity: 0.5 }} tickLine={false} />
            {hasGas && (
              <YAxis yAxisId="gas" orientation="right" tick={{ fill: GAS_COLOR, fontSize: 9 }} width={40} domain={['auto', 'auto']}
                tickFormatter={(v: number) => v.toFixed(v < 10 ? 1 : 0)}
                axisLine={{ stroke: GAS_COLOR, opacity: 0.5 }} tickLine={false} />
            )}
            <Tooltip
              labelFormatter={(label) => `${t.prodMonth}: ${label}`}
              formatter={(value, name) => [
                value === null || value === undefined ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: name === 'gas' ? 3 : 1 }),
                name === 'gas' ? t.prodGas : t.prodOil
              ]}
              contentStyle={{ backgroundColor: '#24180F', borderColor: '#F2E8D5', borderRadius: '6px', fontSize: '10px', color: '#F2E8D5' }}
              itemStyle={{ color: '#D9B36C' }}
            />
            <Legend formatter={(value) => (value === 'gas' ? t.prodGas : t.prodOil)} wrapperStyle={{ fontSize: 9.5, color: '#F2E8D5' }} iconSize={8} />
            <Line yAxisId="oil" type="monotone" dataKey="oil" name="oil" stroke={OIL_COLOR} strokeWidth={2.2}
              dot={{ r: 2, fill: OIL_COLOR }} activeDot={{ r: 4 }} connectNulls />
            {hasGas && (
              <Line yAxisId="gas" type="monotone" dataKey="gas" name="gas" stroke={GAS_COLOR} strokeWidth={1.8}
                dot={{ r: 2, fill: GAS_COLOR }} activeDot={{ r: 4 }} connectNulls />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
};

const SourceToggle: React.FC<{ value: Source; onChange: (source: Source) => void; t: Strings }> = ({ value, onChange, t }) => (
  <div className="ml-auto flex rounded-xs border border-[#F2E8D5]/35 overflow-hidden">
    {(['anh', 'sim'] as Source[]).map((source) => (
      <button key={source} type="button" onClick={() => onChange(source)} aria-pressed={value === source}
        className={`px-1.5 py-0.5 text-[9.5px] font-semibold ${value === source ? 'bg-[#2F7D32] text-[#F2E8D5]' : 'text-[#D9B36C]'}`}>
        {source === 'anh' ? t.prodSourceAnh : t.prodSourceSim}
      </button>
    ))}
  </div>
);

export const ProductionPanel: React.FC = () => {
  const { t } = useLanguage();
  const series = useLatestProduction();
  const anhAt = useLatestProductionAt();
  const run = useWellSimStore((state) => state.run);
  const runAt = useWellSimStore((state) => state.runAt);
  const [pinned, setPinned] = useState<Source | null>(null);
  const compact = series.length > 1;

  // New data from either source shows itself; the toggle pins a choice.
  useEffect(() => setPinned(null), [anhAt, runAt]);
  const both = Boolean(run) && series.length > 0;
  const newest: Source = run && runAt > anhAt ? 'sim' : 'anh';
  const source: Source = run ? (series.length ? pinned ?? newest : 'sim') : 'anh';

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg">
      <div className="shrink-0 mb-1.5 pb-1.5 border-b border-[#F2E8D5]/30 flex items-center gap-1.5">
        <TrendingUp className="w-4 h-4 text-[#D9B36C] shrink-0" />
        <h2 className="text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">
          {source === 'sim' ? t.prodSimTitle : t.prodTitle}
        </h2>
        {both && <SourceToggle value={source} onChange={setPinned} t={t} />}
      </div>

      {source === 'sim' && run ? (
        <SimulationCharts run={run} />
      ) : series.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-2 px-4">
          <MessageSquareText className="w-6 h-6 text-[#D9B36C]/70" />
          <p className="text-[11px] text-[#F2E8D5]/80">{t.prodEmpty}</p>
          <p className="text-[10px] text-[#D9B36C]/70 italic">{t.prodEmptyExample}</p>
        </div>
      ) : (
        <div className={`flex-1 min-h-0 ${compact ? 'overflow-y-auto pr-1 space-y-3' : 'flex flex-col'}`}>
          {series.map((s) => (
            <SeriesChart key={`${s.kind}-${s.fields.join('|')}`} series={s} compact={compact} />
          ))}
        </div>
      )}

      <p className="shrink-0 pt-1.5 mt-1 border-t border-[#F2E8D5]/20 text-[9px] text-[#F2E8D5]/55">
        {source === 'sim' ? t.prodSimNote : `${t.productionNote} · ANH-Produccion-Fiscalizada-2026`}
      </p>
    </div>
  );
};
