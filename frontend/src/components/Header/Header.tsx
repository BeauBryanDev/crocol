import React from 'react';
import { useLanguage } from '../../i18n/useLanguage';
import { Gauge, Globe } from 'lucide-react';
import crocolAvatar from '../../assets/Crocol_Avatar.jpg';
import anhLogo from '../../assets/ANH.png';
import oilTowerIcon from '../../assets/oil_towerr.svg';
import oilContainerIcon from '../../assets/oil_container.svg';
import colombiaIcon from '../../assets/colombia.svg';
import rockIcon from '../../assets/rock_icon.svg';
import OilWell from '../../assets/oil_well.svg';
import SGC from '../../assets/SGC.webp'

const ANH_HOME_URL = 'https://www.anh.gov.co/en/';

const SOURCE_LINKS = [
  {
    href: 'https://geovisor.anh.gov.co/tierras/',
    icon: anhLogo,
    label: 'srcAnhGeovisor',
  },
  {
    href: 'https://app.powerbi.com/view?r=eyJrIjoiNjZiYWMyMDMtZjU5My00NDFlLWE0YTctY2NmNmVjYjc3OWU1IiwidCI6IjZiZGViMzBlLTA2NDQtNDQyYi1hNjIyLTllNzEwYzM2ODFmMSIsImMiOjR9',
    icon: oilTowerIcon,
    label: 'srcAnhPowerBi',
  },
  {
    href: 'https://www.anh.gov.co/es/operaciones-y-regal%C3%ADas/datos-y-estadisticas/',
    icon: oilContainerIcon,
    label: 'srcAnhStats',
  },
  {
    href: 'https://datos.sgc.gov.co/',
    icon: colombiaIcon,
    label: 'srcSgcData',
  },
  {
    href: 'https://datos.sgc.gov.co/search?tags=Geociencias%2520B%25C3%25A1sicas',
    icon: rockIcon,
    label: 'srcSgcGeoscience',
  },
] as const;

interface HeaderProps {
  onOpenKnowMore: () => void;
  onFocusChat: () => void;
  onOpenWellSim: () => void;
  wellSimOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenKnowMore,
  onFocusChat,
  onOpenWellSim,
  wellSimOpen
}) => {
  const { language, toggleLanguage, t } = useLanguage();

  return (
    <header className="w-full bg-[#2F7D32] border-b-2 border-[#F2E8D5] text-[#F2E8D5] px-4 py-2.5 shadow-md flex items-center justify-between z-40">
      {/* Left side: Avatar, Brand, Title, Nav Links */}
      <div className="flex items-center gap-3 md:gap-4 flex-wrap">
        {/* Avatar */}
        <div className="w-[45px] h-[45px] rounded-full overflow-hidden border-2 border-[#F2E8D5] bg-[#24180F] shadow-sm shrink-0">
          <img
            src={crocolAvatar}
            alt="Crocol Mascot Avatar"
            className="w-full h-full object-cover"
            referrerPolicy="no-referrer"
          />
        </div>

        {/* Wordmark CROCOL */}
        <h1 className="text-xl md:text-2xl font-black tracking-wider text-[#D9B36C] font-serif-academic leading-none drop-shadow-xs">
          CROCOL
        </h1>

        {/* App Title Subtitle */}
        <div className="hidden lg:block text-[11px] font-semibold tracking-wider text-[#F2E8D5] uppercase opacity-95">
          {t.appSubtitle}
        </div>

        {/* Divider */}
        <div className="hidden md:block h-5 w-px bg-[#F2E8D5]/40" />

        {/* Know More link */}
        <button
          onClick={onOpenKnowMore}
          className="text-xs md:text-sm font-medium text-[#F2E8D5] hover:text-[#D9B36C] underline decoration-[#F2E8D5]/60 hover:decoration-[#D9B36C] transition-colors"
        >
          {t.navKnowMore}
        </button>

        {/* Divider */}
        <div className="hidden md:block h-5 w-px bg-[#F2E8D5]/40" />

        {/* ANH link */}
        <a
          href={ANH_HOME_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs md:text-sm font-semibold tracking-wide text-[#F2E8D5] hover:text-[#D9B36C] transition-colors"
        >
          {t.navANH}
        </a>

        {/* Divider */}
        <div className="hidden md:block h-5 w-px bg-[#F2E8D5]/40" />

        {/* Well simulator */}
        <button
          onClick={onOpenWellSim}
          aria-pressed={wellSimOpen}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs md:text-sm font-semibold transition-colors ${
            wellSimOpen
              ? 'bg-[#D9B36C] text-[#24180F] border-[#D9B36C]'
              : 'border-[#F2E8D5]/60 text-[#F2E8D5] hover:text-[#D9B36C] hover:border-[#D9B36C]'
          }`}
        >
          <Gauge className="w-3.5 h-3.5" />
          {t.wsHeaderButton}
        </button>
      </div>

      {/* Right side: Language Switcher and Chat with us button */}
      <div className="flex items-center gap-2.5 md:gap-3 shrink-0">
        {/* Corpus data sources, each opens in a new tab */}
        <nav aria-label={t.srcLinksLabel} className="hidden md:flex items-center gap-3">
          {SOURCE_LINKS.map(({ href, icon, label }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              title={t[label]}
              aria-label={t[label]}
              className="w-9 h-9 rounded-md bg-[#F2E8D5] p-1 border border-[#F2E8D5] hover:border-[#D9B36C] hover:scale-110 transition-all shadow-xs"
            >
              <img src={icon} alt={t[label]} className="w-full h-full object-contain" />
            </a>
          ))}
        </nav>

        {/* Bilingual Language Switcher Toggle */}
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#24180F]/40 border border-[#F2E8D5]/60 hover:border-[#D9B36C] text-[#F2E8D5] hover:text-[#D9B36C] text-xs font-bold transition-all shadow-xs"
          title={language === 'es' ? 'Cambiar a Inglés' : 'Switch to Spanish'}
          aria-label="Toggle language"
        >
          <Globe className="w-3.5 h-3.5 text-[#D9B36C]" />
          <span className="uppercase">{language === 'es' ? 'ES | EN' : 'EN | ES'}</span>
        </button>

        {/* Chat with us button with round yellow chat icon matching mockup */}
        <button
          onClick={onFocusChat}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-[#F2E8D5] bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] font-semibold text-xs md:text-sm shadow-sm transition-all active:scale-95"
        >
          <div className="w-4 h-4 rounded-full bg-[#ffd600] flex items-center justify-center shrink-0">
            <span className="w-2.5 h-0.5 bg-[#24180F] rounded-full inline-block" />
          </div>
          <span>{t.chatWithUs}</span>
        </button>
      </div>
    </header>
  );
};
