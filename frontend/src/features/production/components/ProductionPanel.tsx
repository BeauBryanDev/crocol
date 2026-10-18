import React, { useState } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { HISTORICAL_PRODUCTION_DATA } from '../data/productionData';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from 'recharts';
import { TrendingUp, ChevronDown, Sparkles } from 'lucide-react';

interface ProductionPanelProps {
  onInvestigateField?: (fieldName: string) => void;
  selectedFieldKey?: string;
}

export const ProductionPanel: React.FC<ProductionPanelProps> = ({
  onInvestigateField,
  selectedFieldKey = 'rubiales'
}) => {
  const { language, t } = useLanguage();
  const [currentFieldKey, setCurrentFieldKey] = useState<string>(selectedFieldKey);

  const fieldData = HISTORICAL_PRODUCTION_DATA[currentFieldKey] || HISTORICAL_PRODUCTION_DATA.rubiales;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const customTooltipFormatter = (value: any, name: any): [string, string] => {
    if (value === undefined || value === null) return ['-', String(name || '')];
    const num = Number(value);
    const label =
      name === 'oilBopd'
        ? t.prodOil
        : name === 'gasMpcd'
        ? t.prodGas
        : t.prodWater;
    return [`${num.toLocaleString()} ${name === 'oilBopd' ? 'bopd' : name === 'gasMpcd' ? 'Mpcd' : 'bwpd'}`, label];
  };

  return (
    <div className="flex flex-col h-full bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg">
      {/* Header with Field Selector matching mockup */}
      <div className="mb-1.5 pb-1.5 border-b border-[#F2E8D5]/30 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <TrendingUp className="w-4 h-4 text-[#D9B36C] shrink-0" />
          <h2 className="text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">
            {t.prodTitle} - {fieldData.fieldName}
          </h2>
        </div>

        {/* Field Selector Dropdown */}
        <div className="relative shrink-0">
          <select
            value={currentFieldKey}
            onChange={(e) => setCurrentFieldKey(e.target.value)}
            className="appearance-none bg-[#18100a] text-[#F2E8D5] border border-[#F2E8D5]/40 rounded-md px-2.5 py-1 pr-6 text-[10px] font-semibold focus:outline-hidden focus:border-[#D9B36C] cursor-pointer"
          >
            {Object.entries(HISTORICAL_PRODUCTION_DATA).map(([key, data]) => (
              <option key={key} value={key}>
                {data.fieldName}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-[#D9B36C] absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </div>

      {/* Metric Legend matching mockup */}
      <div className="flex items-center justify-center gap-4 py-1 text-[10px]">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#4caf50] border border-[#F2E8D5]" />
          <span className="text-[#F2E8D5] font-medium">{t.prodOil}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#d9b36c] border border-[#F2E8D5]" />
          <span className="text-[#F2E8D5] font-medium">{t.prodGas}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#42a5f5] border border-[#F2E8D5]" />
          <span className="text-[#F2E8D5] font-medium">{t.prodWater}</span>
        </div>
      </div>

      {/* Dual Axis Time-Series Recharts Chart */}
      <div className="flex-1 w-full min-h-[160px] pt-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={fieldData.observations}
            margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          >
            <CartesianGrid stroke="#F2E8D5" strokeOpacity={0.12} strokeDasharray="3 3" />
            
            {/* X Axis: Years */}
            <XAxis
              dataKey="year"
              stroke="#D9B36C"
              tick={{ fill: '#D9B36C', fontSize: 9 }}
              tickLine={{ stroke: '#F2E8D5', opacity: 0.3 }}
              axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }}
            />

            {/* Left Y Axis: Oil (bopd) */}
            <YAxis
              yAxisId="left"
              stroke="#D9B36C"
              tick={{ fill: '#D9B36C', fontSize: 9 }}
              tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
              tickLine={{ stroke: '#F2E8D5', opacity: 0.3 }}
              axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }}
              label={{
                value: t.prodAxisOil,
                angle: -90,
                position: 'insideLeft',
                fill: '#D9B36C',
                fontSize: 9,
                offset: 15
              }}
            />

            {/* Right Y Axis: Gas & Water */}
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#D9B36C"
              tick={{ fill: '#D9B36C', fontSize: 9 }}
              tickLine={{ stroke: '#F2E8D5', opacity: 0.3 }}
              axisLine={{ stroke: '#F2E8D5', opacity: 0.4 }}
              label={{
                value: t.prodAxisGasWater,
                angle: 90,
                position: 'insideRight',
                fill: '#D9B36C',
                fontSize: 9,
                offset: 5
              }}
            />

            {/* Tooltip */}
            <Tooltip
              formatter={customTooltipFormatter}
              labelFormatter={(label) => `${language === 'es' ? 'Año' : 'Year'}: ${label}`}
              contentStyle={{
                backgroundColor: '#24180F',
                borderColor: '#F2E8D5',
                borderRadius: '6px',
                fontSize: '10px',
                color: '#F2E8D5',
                boxShadow: '0 4px 12px rgba(0,0,0,0.6)'
              }}
              itemStyle={{ color: '#D9B36C' }}
            />

            {/* Oil Production Series */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="oilBopd"
              name="oilBopd"
              stroke="#66bb6a"
              strokeWidth={2.2}
              dot={{ r: 3, fill: '#66bb6a', stroke: '#F2E8D5', strokeWidth: 1 }}
              activeDot={{ r: 5, fill: '#F2E8D5', stroke: '#66bb6a', strokeWidth: 2 }}
            />

            {/* Gas Production Series */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="gasMpcd"
              name="gasMpcd"
              stroke="#d9b36c"
              strokeWidth={1.8}
              dot={{ r: 2.5, fill: '#d9b36c', stroke: '#F2E8D5', strokeWidth: 1 }}
              activeDot={{ r: 5, fill: '#F2E8D5', stroke: '#d9b36c', strokeWidth: 2 }}
            />

            {/* Water Production Series */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="waterBwpd"
              name="waterBwpd"
              stroke="#42a5f5"
              strokeWidth={1.8}
              dot={{ r: 2.5, fill: '#42a5f5', stroke: '#F2E8D5', strokeWidth: 1 }}
              activeDot={{ r: 5, fill: '#F2E8D5', stroke: '#42a5f5', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Quick Field Investigation Footer Button */}
      <div className="pt-1.5 mt-1 border-t border-[#F2E8D5]/20 flex items-center justify-between text-[10px]">
        <span className="text-[#F2E8D5]/60 text-[9px] truncate">
          {fieldData.basin} • {fieldData.cumulativeOilMMBO} MMBO
        </span>
        <button
          onClick={() => onInvestigateField?.(fieldData.fieldName)}
          className="text-[#D9B36C] hover:text-[#F2E8D5] flex items-center gap-1 font-semibold hover:underline transition-colors shrink-0"
        >
          <Sparkles className="w-3 h-3 text-[#D9B36C]" />
          <span>{t.investigateField}</span>
        </button>
      </div>
    </div>
  );
};
