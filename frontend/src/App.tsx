import React, { lazy, Suspense, useState } from 'react';
import { LanguageProvider, useLanguage } from './i18n/useLanguage';
import { Header } from './components/Header/Header';
import { Footer } from './components/Footer/Footer';
import { InfoModal, ModalType } from './components/InfoModals/InfoModal';
import { StratigraphicColumn } from './features/stratigraphy/components/StratigraphicColumn';
import { ChatPanel } from './features/chat/components/ChatPanel';
import { ProductionPanel } from './features/production/components/ProductionPanel';
import { GeologicalFormation } from './types/stratigraphy.types';
import { PendingQuestion } from './types/chat.types';
import { UiContext, WellParams } from './types/api.types';
import { WellSimForm } from './features/well-sim/components/WellSimForm';
import { WellSimResults } from './features/well-sim/components/WellSimResults';
import { useWellSimStore } from './features/well-sim/store/wellSimStore';
import { useMapOverlayStore } from './features/map-overlay/store/mapOverlayStore';
import { CrackResultsPanel } from './features/vision/components/CrackResultsPanel';
import { Layers, Bot, Map, TrendingUp } from 'lucide-react';

// MapLibre is ~1 MB: load the map panel in its own chunk, after the chat.
const GeologicalMapPanel = lazy(() =>
  import('./features/geological-map/components/GeologicalMapPanel').then((m) => ({ default: m.GeologicalMapPanel }))
);

type MobileTab = 'stratigraphy' | 'chat' | 'map' | 'production';

const CrocolAppContent: React.FC = () => {
  const { language } = useLanguage();
  const [modalType, setModalType] = useState<ModalType>(null);
  const [selectedFormation, setSelectedFormation] = useState<GeologicalFormation | null>(null);
  const [investigatingFormation, setInvestigatingFormation] = useState<GeologicalFormation | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<PendingQuestion | null>(null);
  const wellSimOpen = useWellSimStore((state) => state.formOpen);
  const mapOverlay = useMapOverlayStore((state) => state.active);
  const setWellSimOpen = useWellSimStore((state) => state.setFormOpen);
  const [mobileTab, setMobileTab] = useState<MobileTab>('chat');

  const handleInvestigateFormation = (formation: GeologicalFormation) => {
    setSelectedFormation(formation);
    setInvestigatingFormation(formation);
    setMobileTab('chat');
  };

  const askCrocol = (question: string, uiContext?: UiContext) => {
    setPendingQuestion({ text: question, uiContext });
    setMobileTab('chat');
  };

  const askAboutWell = (question: string, well: WellParams, contextLabel: string) => {
    setPendingQuestion({ text: question, well, contextLabel });
    setMobileTab('chat');
  };

  // On phones the form lives in the Column tab, over the stratigraphy.
  const toggleWellSim = () => {
    const open = !wellSimOpen;
    setWellSimOpen(open);
    if (open) setMobileTab('stratigraphy');
  };

  // Each panel is mounted once; on small screens only the active tab is shown.
  const panelClass = (tab: MobileTab, mobileHeight: string) =>
    `${mobileTab === tab ? 'block' : 'hidden'} lg:block ${mobileHeight}`;

  const tabButton = (tab: MobileTab, icon: React.ReactNode, label: string) => (
    <button
      onClick={() => setMobileTab(tab)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
        mobileTab === tab
          ? 'bg-[#2F7D32] text-[#F2E8D5] border border-[#F2E8D5]'
          : 'text-[#D9B36C] hover:text-[#F2E8D5]'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="min-h-screen bg-[#24180F] text-[#D9B36C] flex flex-col font-sans selection:bg-[#2F7D32] selection:text-[#F2E8D5]">
      <Header
        onOpenKnowMore={() => setModalType('know-more')}
        onFocusChat={() => {
          setMobileTab('chat');
          document.getElementById('crocol-chat-input')?.focus();
        }}
        onOpenWellSim={toggleWellSim}
        wellSimOpen={wellSimOpen}
      />

      <div className="lg:hidden flex items-center justify-around bg-[#18100a] border-b border-[#F2E8D5]/30 p-1 text-[11px] font-semibold">
        {tabButton('stratigraphy', <Layers className="w-3.5 h-3.5" />, language === 'es' ? 'Columna' : 'Column')}
        {tabButton('chat', <Bot className="w-3.5 h-3.5" />, 'Chat')}
        {tabButton('map', <Map className="w-3.5 h-3.5" />, language === 'es' ? 'Mapa' : 'Map')}
        {tabButton('production', <TrendingUp className="w-3.5 h-3.5" />, language === 'es' ? 'Producción' : 'Production')}
      </div>

      <main className="flex-1 p-2 md:p-3 overflow-hidden">
        <div className="flex flex-col lg:grid lg:grid-cols-12 gap-2.5 lg:h-[calc(100vh-100px)] lg:min-h-[640px]">
          <div className={`relative lg:col-span-3 lg:h-full ${panelClass('stratigraphy', 'h-[620px]')}`}>
            <StratigraphicColumn
              selectedFormationId={selectedFormation?.id}
              onSelectFormation={setSelectedFormation}
              onInvestigateFormation={handleInvestigateFormation}
            />
            {wellSimOpen && (
              <div className="absolute inset-0 z-20">
                <WellSimForm onAsk={askAboutWell} />
              </div>
            )}
          </div>

          <div className={`lg:col-span-5 lg:h-full ${panelClass('chat', 'h-[calc(100dvh-150px)] min-h-[480px]')}`}>
            <ChatPanel
              investigatingFormation={investigatingFormation}
              onClearInvestigatingFormation={() => setInvestigatingFormation(null)}
              pendingQuestion={pendingQuestion}
              onClearPendingQuestion={() => setPendingQuestion(null)}
              onShowOnMap={() => setMobileTab('map')}
            />
          </div>

          <div className="contents lg:col-span-4 lg:h-full lg:flex lg:flex-col lg:gap-2.5">
            <div className={`relative lg:h-[52%] ${panelClass('map', 'h-[560px]')}`}>
              <Suspense fallback={<div className="h-full rounded-lg border border-[#F2E8D5] bg-[#24180F]" />}>
                <GeologicalMapPanel onInvestigateFeature={askCrocol} />
              </Suspense>
              {mapOverlay && (
                <div className="absolute inset-0 z-20">
                  {mapOverlay === 'wellsim' ? <WellSimResults /> : <CrackResultsPanel />}
                </div>
              )}
            </div>

            <div className={`lg:h-[48%] ${panelClass('production', 'h-[520px]')}`}>
              <ProductionPanel />
            </div>
          </div>
        </div>
      </main>

      <Footer
        onOpenDoc={() => setModalType('documentation')}
        onOpenSources={() => setModalType('data-sources')}
        onOpenMethodology={() => setModalType('methodology')}
        onOpenHelp={() => setModalType('help')}
      />

      <InfoModal type={modalType} onClose={() => setModalType(null)} />
    </div>
  );
};

export default function App() {
  return (
    <LanguageProvider>
      <CrocolAppContent />
    </LanguageProvider>
  );
}
