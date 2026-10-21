import React from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { MapPin, BookOpen, Layers, BarChart3, FileText } from 'lucide-react';

interface QuickActionsProps {
  onActionClick: (prompt: string) => void;
  disabled?: boolean;
}

export const QuickActions: React.FC<QuickActionsProps> = ({ onActionClick, disabled }) => {
  const { language, t } = useLanguage();

  const actions = [
    {
      id: 'wells',
      label: t.quickActionWells,
      icon: MapPin,
      prompt: language === 'es' ? '¿Qué pozos hay en el municipio de Barrancabermeja?' : 'Which wells are in the municipality of Barrancabermeja?'
    },
    {
      id: 'basins',
      label: t.quickActionBasins,
      icon: BookOpen,
      prompt: language === 'es' ? '¿Cómo evolucionó tectónicamente la cuenca del Valle Medio del Magdalena?' : 'How did the Middle Magdalena Valley basin evolve tectonically?'
    },
    {
      id: 'formations',
      label: t.quickActionFormations,
      icon: Layers,
      prompt: language === 'es' ? 'Describe la columna estratigráfica del VMM y sus rocas generadoras' : 'Describe the VMM stratigraphic column and its source rocks'
    },
    {
      id: 'fields',
      label: t.quickActionFields,
      // Custom oil derrick icon or Lucide icon
      icon: () => (
        <svg className="w-4 h-4 text-[#D9B36C]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v4M8 6h8M6 22l4-16h4l4 16M6 14h12M4 22h16" />
        </svg>
      ),
      prompt: language === 'es' ? '¿Cuáles son los principales campos petroleros del VMM y sus yacimientos?' : 'What are the main oil fields of the VMM and their reservoirs?'
    },
    {
      id: 'production',
      label: t.quickActionProduction,
      icon: BarChart3,
      prompt: language === 'es' ? '¿Cómo ha evolucionado la producción de crudo y gas del campo Casabe en 2025 y 2026?' : 'How have oil and gas production evolved at the Casabe field in 2025 and 2026?'
    },
    {
      id: 'docs',
      label: t.quickActionDocs,
      icon: FileText,
      prompt: language === 'es' ? '¿Qué obligaciones fija un contrato E&P de la ANH en el VMM?' : 'What obligations does an ANH E&P contract in the VMM set?'
    }
  ];

  return (
    <div className="grid grid-cols-2 gap-2 my-2.5">
      {actions.map((act) => {
        const IconComponent = act.icon;
        return (
          <button
            key={act.id}
            disabled={disabled}
            onClick={() => onActionClick(act.prompt)}
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-[#18100a] border border-[#F2E8D5]/30 text-[#D9B36C] hover:text-[#F2E8D5] hover:border-[#D9B36C] hover:bg-[#2F7D32]/20 transition-all text-[11px] font-medium text-left shadow-xs active:scale-[0.98] disabled:opacity-50"
          >
            <span className="shrink-0 text-[#D9B36C]">
              <IconComponent className="w-4 h-4" />
            </span>
            <span className="truncate">{act.label}</span>
          </button>
        );
      })}
    </div>
  );
};
