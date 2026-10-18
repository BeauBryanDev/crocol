import React from 'react';
import { X, BookOpen, Database, Sliders, Info, ShieldCheck } from 'lucide-react';
import { useLanguage } from '../../i18n/useLanguage';

export type ModalType = 'know-more' | 'anh' | 'documentation' | 'data-sources' | 'methodology' | 'help' | null;

interface InfoModalProps {
  type: ModalType;
  onClose: () => void;
}

export const InfoModal: React.FC<InfoModalProps> = ({ type, onClose }) => {
  const { language } = useLanguage();

  if (!type) return null;

  const contentMap: Record<
    Exclude<ModalType, null>,
    { title: string; subtitle: string; icon: React.ComponentType<{ className?: string }>; body: React.ReactNode }
  > = {
    'know-more': {
      title: language === 'es' ? 'Acerca de Crocol' : 'About Crocol',
      subtitle: language === 'es' ? 'Agente de IA Multi-Grafo en Geología del Petróleo en Colombia' : 'Multi-Graph AI Expert Agent in Colombian Petroleum Geology',
      icon: Info,
      body: (
        <div className="space-y-3 text-xs leading-relaxed text-[#F2E8D5]/90">
          <p>
            {language === 'es'
              ? 'Crocol es una plataforma de inteligencia artificial especializada en el análisis estratigráfico, modelamiento de cuencas sedimentarias, pozos exploratorios y producción de hidrocarburos en Colombia, con especial énfasis en el Valle Medio del Magdalena (VMM).'
              : 'Crocol is an AI-powered expert agent specialized in stratigraphic interpretation, sedimentary basin modeling, exploratory well analysis, and hydrocarbon production in Colombia, with core focus on the Middle Magdalena Valley (VMM).'}
          </p>
          <div className="p-3 bg-[#18100a] border border-[#F2E8D5]/30 rounded-md">
            <h4 className="font-bold text-[#D9B36C] mb-1">
              {language === 'es' ? 'Arquitectura Multi-Grafo' : 'Multi-Graph Architecture'}
            </h4>
            <ul className="list-disc pl-4 space-y-1 text-[11px]">
              <li>
                {language === 'es'
                  ? 'Grafo Estratigráfico: Relaciones temporales y facies desde el Precámbrico hasta el Cuaternario.'
                  : 'Stratigraphic Graph: Temporal sequences and lithofacies from Precambrian to Quaternary.'}
              </li>
              <li>
                {language === 'es'
                  ? 'Grafo Geoespacial: Pozos, bloques de exploración y cuencas sedimentarias georreferenciadas.'
                  : 'Geospatial Graph: Georeferenced well coordinates, exploratory blocks, and basin boundaries.'}
              </li>
              <li>
                {language === 'es'
                  ? 'Grafo de Producción: Series de tiempo mensuales de crudo (bopd), gas (Mpcd) y agua (bwpd).'
                  : 'Production Graph: Monthly time series for crude oil (bopd), gas (Mpcd), and water (bwpd).'}
              </li>
            </ul>
          </div>
        </div>
      )
    },
    anh: {
      title: language === 'es' ? 'Agencia Nacional de Hidrocarburos (ANH)' : 'National Hydrocarbons Agency (ANH)',
      subtitle: language === 'es' ? 'Integración y Datos Oficiales de Colombia' : 'Official Colombian Petroleum Data Integration',
      icon: ShieldCheck,
      body: (
        <div className="space-y-3 text-xs leading-relaxed text-[#F2E8D5]/90">
          <p>
            {language === 'es'
              ? 'Todos los datos de pozos, contratos de exploración, estratigrafía oficial y registros históricos se fundamentan en el Banco de Información Petrolera (EPIS / BIP) de la Agencia Nacional de Hidrocarburos de Colombia.'
              : 'All exploratory well records, E&P contracts, official stratigraphy, and historical production data are aligned with the National Petroleum Information Bank (EPIS / BIP) of Colombia’s ANH.'}
          </p>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="p-2.5 bg-[#18100a] border border-[#F2E8D5]/20 rounded-md">
              <span className="font-bold text-[#D9B36C] block">EPIS / BIP</span>
              <span>{language === 'es' ? 'Más de 14,000 pozos con registros eléctricos.' : '14,000+ well logs and petrophysical tracks.'}</span>
            </div>
            <div className="p-2.5 bg-[#18100a] border border-[#F2E8D5]/20 rounded-md">
              <span className="font-bold text-[#D9B36C] block">Cartografía SGC</span>
              <span>{language === 'es' ? 'Atlas Geológico de Colombia escala 1:1,000,000.' : 'Geological Atlas of Colombia 1:1,000,000 scale.'}</span>
            </div>
          </div>
        </div>
      )
    },
    documentation: {
      title: language === 'es' ? 'Documentación Técnica' : 'Technical Documentation',
      subtitle: language === 'es' ? 'Guía de uso y especificaciones científicas' : 'User guide and scientific specifications',
      icon: BookOpen,
      body: (
        <div className="space-y-2.5 text-xs text-[#F2E8D5]/90">
          <p>
            {language === 'es'
              ? 'La aplicación Crocol integra tres paneles interactivos sincronizados:'
              : 'The Crocol workstation integrates three synchronized interactive workspaces:'}
          </p>
          <ol className="list-decimal pl-4 space-y-1 text-[11px]">
            <li>
              <strong>{language === 'es' ? 'Columna Estratigráfica:' : 'Stratigraphic Column:'}</strong>{' '}
              {language === 'es'
                ? 'Permite explorar las unidades geológicas desde el Cuaternario hasta el Basamento con patrones litológicos realistas. Al hacer clic se despliegan propiedades petrofísicas y el botón "Investigar con Crocol".'
                : 'Interactive SVG column with realistic AAPG/USGS lithology patterns. Clicking any unit opens petrophysical attributes and the "Investigate with Crocol" trigger.'}
            </li>
            <li>
              <strong>{language === 'es' ? 'Chat con Crocol:' : 'Crocol AI Chat:'}</strong>{' '}
              {language === 'es'
                ? 'Agente conversacional especializado con acciones rápidas para pozos, cuencas, formaciones y documentos.'
                : 'Conversational scientific expert with one-click quick actions and full bilingual context.'}
            </li>
            <li>
              <strong>{language === 'es' ? 'Cartografía y Producción:' : 'Map & Production Analytics:'}</strong>{' '}
              {language === 'es'
                ? 'Mapa geológico interactivo con capas de pozos y cuencas, y gráfica multieje de producción histórica Recharts.'
                : 'Interactive geological map of Colombia and dual-axis Recharts time-series visualization.'}
            </li>
          </ol>
        </div>
      )
    },
    'data-sources': {
      title: language === 'es' ? 'Fuentes de Datos' : 'Data Sources',
      subtitle: language === 'es' ? 'Entidades y referencias autoritativas' : 'Authoritative institutions and literature',
      icon: Database,
      body: (
        <div className="space-y-2.5 text-xs text-[#F2E8D5]/90">
          <ul className="space-y-2 text-[11px]">
            <li className="p-2 bg-[#18100a] border border-[#F2E8D5]/20 rounded-md">
              <strong className="text-[#D9B36C]">Agencia Nacional de Hidrocarburos (ANH):</strong>{' '}
              {language === 'es'
                ? 'Estadísticas de producción mensual, mapas de contratos de tierras y fichas de pozos.'
                : 'Monthly production reports, land contracts, and official well catalogs.'}
            </li>
            <li className="p-2 bg-[#18100a] border border-[#F2E8D5]/20 rounded-md">
              <strong className="text-[#D9B36C]">Servicio Geológico Colombiano (SGC):</strong>{' '}
              {language === 'es'
                ? 'Mapa Geológico de Colombia 2020 y Léxico Estratigráfico.'
                : 'Geological Map of Colombia 2020 and Stratigraphic Lexicon.'}
            </li>
            <li className="p-2 bg-[#18100a] border border-[#F2E8D5]/20 rounded-md">
              <strong className="text-[#D9B36C]">Literatura de Cuencas:</strong>{' '}
              {language === 'es'
                ? 'Publicaciones de la Asociación Colombiana de Geólogos y Geofísicos del Petróleo (ACGGP).'
                : 'Publications by the Colombian Association of Petroleum Geologists and Geophysicists (ACGGP).'}
            </li>
          </ul>
        </div>
      )
    },
    methodology: {
      title: language === 'es' ? 'Metodología' : 'Methodology',
      subtitle: language === 'es' ? 'Integración y gobernanza de datos geológicos' : 'Geological data governance and retrieval',
      icon: Sliders,
      body: (
        <div className="space-y-2.5 text-xs text-[#F2E8D5]/90">
          <p>
            {language === 'es'
              ? 'Crocol opera bajo una rigurosa política de integridad científica:'
              : 'Crocol adheres to strict scientific integrity standards:'}
          </p>
          <ul className="list-disc pl-4 space-y-1 text-[11px]">
            <li>
              {language === 'es'
                ? 'Validación explícita: Toda formación geológica indica su estado de validación (validado, en revisión o sin verificar).'
                : 'Explicit validation: Every formation indicates its verification status (validated, under review, or unverified).'}
            </li>
            <li>
              {language === 'es'
                ? 'Trazabilidad de fuentes: Las respuestas de Crocol citan explícitamente reportes ANH, mapas SGC o artículos indexados.'
                : 'Source provenance: Assistant answers cite ANH technical reports, SGC publications, and peer-reviewed studies.'}
            </li>
            <li>
              {language === 'es'
                ? 'Sin alucinaciones numéricas: Las series de producción corresponden a los registros históricos consolidados de los campos principales.'
                : 'Ground truth data: Production observations reflect historical reported data from major Colombian fields.'}
            </li>
          </ul>
        </div>
      )
    },
    help: {
      title: language === 'es' ? 'Centro de Ayuda' : 'Help Center',
      subtitle: language === 'es' ? 'Navegación e interacción en la estación de trabajo' : 'Workstation navigation and shortcuts',
      icon: Info,
      body: (
        <div className="space-y-2 text-xs text-[#F2E8D5]/90">
          <p>
            {language === 'es'
              ? 'Consejos para interactuar con la plataforma:'
              : 'Workstation tips:'}
          </p>
          <ul className="list-disc pl-4 space-y-1.5 text-[11px]">
            <li>
              <strong>{language === 'es' ? 'Columna Estratigráfica:' : 'Stratigraphy:'}</strong>{' '}
              {language === 'es'
                ? 'Haz clic en cualquier formación para abrir su ficha completa y transferirla al chat con un solo clic.'
                : 'Click any formation in the column to inspect petrophysical details and send directly to chat.'}
            </li>
            <li>
              <strong>{language === 'es' ? 'Acciones Rápidas:' : 'Quick Actions:'}</strong>{' '}
              {language === 'es'
                ? 'Utiliza los 6 botones en la parte inferior del chat para consultas recurrentes.'
                : 'Use the 6 preset buttons at the bottom of the chat panel for frequent queries.'}
            </li>
            <li>
              <strong>{language === 'es' ? 'Selector de Campo:' : 'Field Selector:'}</strong>{' '}
              {language === 'es'
                ? 'Usa el menú desplegable en la gráfica de producción para alternar entre Campo Rubiales, Cusiana, Caño Limón, La Cira-Infantas y Castilla.'
                : 'Use the dropdown menu above the production chart to switch between Rubiales, Cusiana, Caño Limón, La Cira-Infantas, and Castilla.'}
            </li>
          </ul>
        </div>
      )
    }
  };

  const item = contentMap[type];
  const IconComponent = item.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs">
      <div
        className="w-full max-w-lg bg-[#24180F] border-2 border-[#F2E8D5] rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="px-5 py-3.5 bg-[#2F7D32] border-b border-[#F2E8D5]/30 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-[#24180F]/40 border border-[#F2E8D5]/40 text-[#D9B36C]">
              <IconComponent className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#F2E8D5] font-serif-academic leading-tight">
                {item.title}
              </h3>
              <p className="text-[10px] text-[#D9B36C] font-medium leading-none mt-0.5">
                {item.subtitle}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-[#F2E8D5] hover:text-[#D9B36C] hover:bg-[#24180F]/30 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-5 overflow-y-auto">
          {item.body}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 bg-[#18100a] border-t border-[#F2E8D5]/20 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-md bg-[#2F7D32] border border-[#F2E8D5] text-[#F2E8D5] hover:bg-[#256828] text-xs font-semibold shadow-xs transition-colors"
          >
            {language === 'es' ? 'Entendido' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
};
