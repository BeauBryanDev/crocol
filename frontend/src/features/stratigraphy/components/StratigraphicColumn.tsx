import React, { useState } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { GEOLOGICAL_PERIODS, FORMATIONS_DATA } from '../data/formations.data';
import { GeologicalFormation, GeologicalPeriodId } from '../../../types/stratigraphy.types';
import { LithologyPatternDefs } from './LithologyPatternDefs';
import { LithologyLegend } from './LithologyLegend';
import { FormationDetailsModal } from './FormationDetailsModal';
import { Layers } from 'lucide-react';

interface StratigraphicColumnProps {
  selectedFormationId?: string | null;
  onSelectFormation?: (formation: GeologicalFormation) => void;
  onInvestigateFormation?: (formation: GeologicalFormation) => void;
}

interface PeriodDisplayRow {
  periodId: GeologicalPeriodId;
  name: { en: string; es: string };
  color: string;
  textColor: string;
  lithologyText: { en: string; es: string };
  patternId: string;
  faciesText: { en: string; es: string };
  formations: GeologicalFormation[];
}

export const StratigraphicColumn: React.FC<StratigraphicColumnProps> = ({
  selectedFormationId,
  onSelectFormation,
  onInvestigateFormation
}) => {
  const { language, t } = useLanguage();
  const [modalFormation, setModalFormation] = useState<GeologicalFormation | null>(null);

  // Group formations into periods for table rendering matching mockup
  const periodRows: PeriodDisplayRow[] = [
    {
      periodId: 'quaternary',
      name: { en: 'Quaternary', es: 'Cuaternario' },
      color: '#EAD68B',
      textColor: '#1e130a',
      lithologyText: { en: 'Sands, Silts, Gravels', es: 'Arenas\nLimos\nGravas' },
      patternId: 'pattern-sandstone',
      faciesText: { en: 'Fluvial\nDeltaic\nCoastal', es: 'Fluvial\nDeltáica\nCostera' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'quaternary')
    },
    {
      periodId: 'neogene',
      name: { en: 'Neogene', es: 'Neógeno' },
      color: '#E4A836',
      textColor: '#1e130a',
      lithologyText: { en: 'Sandstones\nShales', es: 'Areniscas\nLutitas' },
      patternId: 'pattern-shale',
      faciesText: { en: 'Shallow\nMarine', es: 'Marino\nSomero' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'neogene')
    },
    {
      periodId: 'paleogene',
      name: { en: 'Paleogene', es: 'Paleógeno' },
      color: '#D8975A',
      textColor: '#1e130a',
      lithologyText: { en: 'Sandstones\nShales\nLimestones', es: 'Areniscas\nLutitas\nCalizas' },
      patternId: 'pattern-sandstone',
      faciesText: { en: 'Marine\nPlatform', es: 'Plataforma\nMarina' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'paleogene')
    },
    {
      periodId: 'cretaceous',
      name: { en: 'Cretaceous', es: 'Cretácico' },
      color: '#6A9B6B',
      textColor: '#ffffff',
      lithologyText: { en: 'Sandstones\nShales\nLimestones', es: 'Areniscas\nLutitas\nCalizas' },
      patternId: 'pattern-limestone',
      faciesText: { en: 'Marine\nShelf to Slope', es: 'Marino\nPlataforma\na Talud' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'cretaceous')
    },
    {
      periodId: 'jurassic',
      name: { en: 'Jurassic', es: 'Jurásico' },
      color: '#4A9BB8',
      textColor: '#ffffff',
      lithologyText: { en: 'Sandstones\nShales\nEvaporites', es: 'Areniscas\nLutitas\nEvaporitas' },
      patternId: 'pattern-evaporite',
      faciesText: { en: 'Restricted\nMarine', es: 'Marino\nRestringido' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'jurassic')
    },
    {
      periodId: 'triassic',
      name: { en: 'Triassic', es: 'Triásico' },
      color: '#9F7BB8',
      textColor: '#ffffff',
      lithologyText: { en: 'Sandstones\nShales\nConglomerates', es: 'Areniscas\nLutitas\nConglomerados' },
      patternId: 'pattern-conglomerate',
      faciesText: { en: 'Continental\nto Shallow Marine', es: 'Continental\na Marino\nSomero' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'triassic')
    },
    {
      periodId: 'permian',
      name: { en: 'Permian', es: 'Pérmico' },
      color: '#B2594D',
      textColor: '#ffffff',
      lithologyText: { en: 'Sandstones\nShales\nVolcanics', es: 'Areniscas\nLutitas\nVolcánicas' },
      patternId: 'pattern-volcanic',
      faciesText: { en: 'Continental\n(Desert / Rift)', es: 'Continental\n(Desértico)' },
      formations: FORMATIONS_DATA.filter((f) => f.periodId === 'permian' || f.periodId === 'pre-mesozoic')
    }
  ];

  const handleFormationClick = (formation: GeologicalFormation) => {
    onSelectFormation?.(formation);
    setModalFormation(formation);
  };

  return (
    <div className="flex flex-col h-full bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg">
      <LithologyPatternDefs />

      {/* Panel Header */}
      <div className="mb-2 pb-2 border-b border-[#F2E8D5]/30">
        <div className="flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-[#D9B36C]" />
          <h2 className="text-sm font-bold tracking-tight text-[#F2E8D5] font-serif-academic">
            {t.colTitle}
          </h2>
        </div>
        <p className="text-[11px] text-[#D9B36C]/90 mt-0.5">
          {t.colSubtitle}
        </p>
      </div>

      {/* Stratigraphic Table Container */}
      <div className="flex-1 overflow-y-auto pr-1">
        <table className="w-full border-collapse text-[10px]">
          <thead>
            <tr className="border-b border-[#F2E8D5]/40 text-[#D9B36C] font-semibold text-center uppercase tracking-wider">
              <th className="py-1 px-1 text-left w-[24%]">{t.colPeriod}</th>
              <th className="py-1 px-1 text-left w-[28%]">{t.colLithology}</th>
              <th className="py-1 px-1 text-left w-[24%]">{t.colFacies}</th>
              <th className="py-1 px-1 text-left w-[24%]">{t.colFormations}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F2E8D5]/20">
            {periodRows.map((row) => {
              const isPeriodSelected = row.formations.some((f) => f.id === selectedFormationId);

              return (
                <tr
                  key={row.periodId}
                  className={`transition-colors ${
                    isPeriodSelected ? 'bg-[#F2E8D5]/10' : 'hover:bg-[#18100a]'
                  }`}
                >
                  {/* Period Column with Color Block */}
                  <td className="p-1 align-top">
                    <div
                      className="rounded-xs px-1.5 py-2 font-bold text-center border border-[#F2E8D5]/40 shadow-xs h-full min-h-[50px] flex items-center justify-center"
                      style={{
                        backgroundColor: row.color,
                        color: row.textColor
                      }}
                    >
                      <span className="text-[10px] leading-tight font-semibold tracking-tight">
                        {row.name[language]}
                      </span>
                    </div>
                  </td>

                  {/* Lithology Pattern & Text */}
                  <td className="p-1 align-top">
                    <div className="flex items-start gap-1.5">
                      <svg className="w-5 h-12 rounded-xs border border-[#F2E8D5]/40 shrink-0 shadow-xs">
                        <rect width="100%" height="100%" fill={`url(#${row.patternId})`} />
                      </svg>
                      <div className="text-[9.5px] leading-tight text-[#F2E8D5]/90 whitespace-pre-line">
                        {row.lithologyText[language]}
                      </div>
                    </div>
                  </td>

                  {/* Facies Column */}
                  <td className="p-1 align-top">
                    <div className="text-[9.5px] leading-tight text-[#D9B36C] whitespace-pre-line">
                      {row.faciesText[language]}
                    </div>
                  </td>

                  {/* Formations List Buttons */}
                  <td className="p-1 align-top">
                    <div className="flex flex-col gap-1">
                      {row.formations.length > 0 ? (
                        row.formations.map((formation) => {
                          const isSelected = formation.id === selectedFormationId;
                          return (
                            <button
                              key={formation.id}
                              onClick={() => handleFormationClick(formation)}
                              title={formation.displayName[language]}
                              className={`text-left text-[9.5px] px-1 py-0.5 rounded-xs transition-all leading-tight border ${
                                isSelected
                                  ? 'bg-[#F2E8D5] text-[#24180F] font-bold border-[#F2E8D5] shadow-xs'
                                  : 'text-[#D9B36C] hover:text-[#F2E8D5] hover:bg-[#F2E8D5]/15 border-transparent hover:border-[#F2E8D5]/40'
                              }`}
                            >
                              {formation.displayName[language].length > 22
                                ? `${formation.displayName[language].slice(0, 20)}...`
                                : formation.displayName[language]}
                            </button>
                          );
                        })
                      ) : (
                        <span className="text-[9px] text-[#F2E8D5]/50 italic">
                          {language === 'es' ? 'Fms. asociadas' : 'Associated fms'}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Lithology Legend at Bottom */}
      <LithologyLegend />

      {/* Details Modal on Formation Click */}
      {modalFormation && (
        <FormationDetailsModal
          formation={modalFormation}
          periodMeta={GEOLOGICAL_PERIODS.find((p) => p.id === modalFormation.periodId)}
          onClose={() => setModalFormation(null)}
          onInvestigate={(fmt) => {
            onInvestigateFormation?.(fmt);
          }}
        />
      )}
    </div>
  );
};
