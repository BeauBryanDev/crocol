import React from 'react';
import { useLanguage } from '../../../i18n/useLanguage';

interface LegendItem {
  id: string;
  name: { en: string; es: string };
  patternId: string;
}

const LEGEND_ITEMS: LegendItem[] = [
  { id: 'sandstone', name: { en: 'Sandstone', es: 'Arenisca' }, patternId: 'pattern-sandstone' },
  { id: 'shale', name: { en: 'Shale', es: 'Lutita' }, patternId: 'pattern-shale' },
  { id: 'limestone', name: { en: 'Limestone', es: 'Caliza' }, patternId: 'pattern-limestone' },
  { id: 'conglomerate', name: { en: 'Conglomerate', es: 'Conglomerado' }, patternId: 'pattern-conglomerate' },
  { id: 'evaporite', name: { en: 'Evaporite', es: 'Evaporita' }, patternId: 'pattern-evaporite' },
  { id: 'volcanic', name: { en: 'Volcanic', es: 'Volcánica' }, patternId: 'pattern-volcanic' },
  { id: 'mudstone', name: { en: 'Silt / Clay', es: 'Limo / Arcilla' }, patternId: 'pattern-mudstone' },
  { id: 'coal', name: { en: 'Coal', es: 'Carbón' }, patternId: 'pattern-coal' }
];

export const LithologyLegend: React.FC = () => {
  const { language, t } = useLanguage();

  return (
    <div className="pt-2.5 mt-2 border-t border-[#F2E8D5]/20">
      <h4 className="text-[11px] font-semibold tracking-wide uppercase text-[#D9B36C] mb-2 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-[#D9B36C]" />
        {t.lithologyLegendTitle}
      </h4>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[10px]">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.id} className="flex items-center gap-2">
            <svg className="w-5 h-3.5 rounded-xs border border-[#F2E8D5]/40 shrink-0">
              <rect width="100%" height="100%" fill={`url(#${item.patternId})`} />
            </svg>
            <span className="text-[#F2E8D5]/90 truncate">
              {item.name[language]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
