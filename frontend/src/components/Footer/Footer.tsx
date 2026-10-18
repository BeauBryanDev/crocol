import React from 'react';
import { useLanguage } from '../../i18n/useLanguage';
import { BookOpen, Database, Sliders, HelpCircle } from 'lucide-react';

interface FooterProps {
  onOpenDoc: () => void;
  onOpenSources: () => void;
  onOpenMethodology: () => void;
  onOpenHelp: () => void;
}

export const Footer: React.FC<FooterProps> = ({
  onOpenDoc,
  onOpenSources,
  onOpenMethodology,
  onOpenHelp
}) => {
  const { t } = useLanguage();

  return (
    <footer className="w-full bg-[#2F7D32] border-t-2 border-[#F2E8D5] text-[#F2E8D5] px-4 py-2.5 shadow-inner flex flex-col md:flex-row items-center justify-between gap-3 text-xs z-30">
      {/* Left: Wordmark & Tagline */}
      <div className="flex items-center gap-3">
        <span className="font-black text-sm text-[#D9B36C] font-serif-academic tracking-wider">
          {t.appName}
        </span>
        <span className="text-[11px] font-semibold text-[#F2E8D5]/90 tracking-wide uppercase">
          {t.appSubtitle}
        </span>
      </div>

      {/* Center: Navigation Links with Icons */}
      <div className="flex items-center gap-4 flex-wrap justify-center text-[11px] font-medium">
        <button
          onClick={onOpenDoc}
          className="flex items-center gap-1.5 hover:text-[#D9B36C] transition-colors"
        >
          <BookOpen className="w-3.5 h-3.5 text-[#D9B36C]" />
          <span>{t.footerDocumentation}</span>
        </button>

        <button
          onClick={onOpenSources}
          className="flex items-center gap-1.5 hover:text-[#D9B36C] transition-colors"
        >
          <Database className="w-3.5 h-3.5 text-[#D9B36C]" />
          <span>{t.footerDataSources}</span>
        </button>

        <button
          onClick={onOpenMethodology}
          className="flex items-center gap-1.5 hover:text-[#D9B36C] transition-colors"
        >
          <Sliders className="w-3.5 h-3.5 text-[#D9B36C]" />
          <span>{t.footerMethodology}</span>
        </button>

        <button
          onClick={onOpenHelp}
          className="flex items-center gap-1.5 hover:text-[#D9B36C] transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5 text-[#D9B36C]" />
          <span>{t.footerHelp}</span>
        </button>
      </div>

      {/* Right: Copyright */}
      <div className="text-[10px] text-[#F2E8D5]/80">
        {t.footerCopyright}
      </div>
    </footer>
  );
};
