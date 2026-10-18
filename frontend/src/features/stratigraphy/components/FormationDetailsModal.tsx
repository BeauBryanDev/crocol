import React from 'react';
import { GeologicalFormation, GeologicalPeriodMeta } from '../../../types/stratigraphy.types';
import { useLanguage } from '../../../i18n/useLanguage';
import { X, Layers, Flame, BookOpen, CheckCircle, HelpCircle, ArrowRight } from 'lucide-react';

interface FormationDetailsModalProps {
  formation: GeologicalFormation;
  periodMeta?: GeologicalPeriodMeta;
  onClose: () => void;
  onInvestigate: (formation: GeologicalFormation) => void;
}

export const FormationDetailsModal: React.FC<FormationDetailsModalProps> = ({
  formation,
  periodMeta,
  onClose,
  onInvestigate
}) => {
  const { language, t } = useLanguage();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div
        className="w-full max-w-xl bg-[#24180F] border-2 border-[#F2E8D5] rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="formation-modal-title"
      >
        {/* Header */}
        <div
          className="px-5 py-3.5 border-b border-[#F2E8D5]/30 flex items-center justify-between"
          style={{ backgroundColor: periodMeta ? `${periodMeta.color}22` : '#2F7D32' }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-3.5 h-3.5 rounded-full border border-[#F2E8D5]"
              style={{ backgroundColor: periodMeta?.color || '#D9B36C' }}
            />
            <div>
              <span className="text-[10px] uppercase tracking-wider text-[#D9B36C] font-semibold">
                {periodMeta?.name[language]} • {formation.epochOrAge[language]}
              </span>
              <h3 id="formation-modal-title" className="text-base font-bold text-[#F2E8D5]">
                {formation.displayName[language]}
              </h3>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-[#D9B36C] hover:text-[#F2E8D5] hover:bg-[#F2E8D5]/10 transition-colors"
            aria-label={t.close}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 overflow-y-auto text-xs text-[#F2E8D5]/90">
          {/* Lithology & Facies Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3 rounded-md bg-[#18100a] border border-[#F2E8D5]/20">
              <span className="text-[10px] uppercase font-semibold text-[#D9B36C] block mb-1">
                {t.dominantLithology}
              </span>
              <p className="text-[#F2E8D5] font-medium leading-relaxed">
                {formation.lithologyText[language]}
              </p>
            </div>

            <div className="p-3 rounded-md bg-[#18100a] border border-[#F2E8D5]/20">
              <span className="text-[10px] uppercase font-semibold text-[#D9B36C] block mb-1">
                {t.depositionalEnvironment}
              </span>
              <p className="text-[#F2E8D5] font-medium leading-relaxed">
                {formation.facies[language]}
              </p>
            </div>
          </div>

          {/* Geological Description */}
          <div className="p-3 rounded-md bg-[#18100a] border border-[#F2E8D5]/20">
            <span className="text-[10px] uppercase font-semibold text-[#D9B36C] block mb-1 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              {language === 'es' ? 'Descripción Geológica' : 'Geological Description'}
            </span>
            <p className="text-[#F2E8D5]/90 leading-relaxed text-[11px]">
              {formation.description[language]}
            </p>
          </div>

          {/* Members / Units if present */}
          {formation.members && formation.members.length > 0 && (
            <div className="p-3 rounded-md bg-[#18100a] border border-[#F2E8D5]/20">
              <span className="text-[10px] uppercase font-semibold text-[#D9B36C] block mb-1">
                {t.membersAndUnits}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {formation.members.map((m) => (
                  <span
                    key={m}
                    className="px-2 py-0.5 rounded-xs bg-[#2F7D32]/30 text-[#D9B36C] border border-[#D9B36C]/40 text-[10px]"
                  >
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Petroleum Significance */}
          {formation.petroleumSignificance && (
            <div className="p-3 rounded-md bg-[#2F7D32]/15 border border-[#2F7D32]/60">
              <span className="text-[10px] uppercase font-semibold text-[#D9B36C] flex items-center gap-1.5 mb-1">
                <Flame className="w-3.5 h-3.5 text-[#D9B36C]" />
                {t.petroleumSignificance}
              </span>
              <p className="text-[#F2E8D5] text-[11px] leading-relaxed">
                {formation.petroleumSignificance[language]}
              </p>
            </div>
          )}

          {/* Status & Sources */}
          <div className="flex items-center justify-between pt-1 border-t border-[#F2E8D5]/20 text-[10px]">
            <div className="flex items-center gap-1.5 text-[#D9B36C]">
              {formation.validationStatus === 'validated' ? (
                <CheckCircle className="w-3.5 h-3.5 text-[#6A9B6B]" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5 text-[#E4A836]" />
              )}
              <span>{t[formation.validationStatus]}</span>
            </div>

            <div className="flex items-center gap-1 text-[#F2E8D5]/60">
              <BookOpen className="w-3 h-3" />
              <span>{formation.sourceIds.join(', ')}</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-[#18100a] border-t border-[#F2E8D5]/30 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-md border border-[#F2E8D5]/40 text-[#F2E8D5] hover:bg-[#F2E8D5]/10 text-xs font-medium transition-colors"
          >
            {t.close}
          </button>
          <button
            onClick={() => {
              onInvestigate(formation);
              onClose();
            }}
            className="px-4 py-1.5 rounded-md bg-[#2F7D32] border border-[#F2E8D5] text-[#F2E8D5] hover:bg-[#256828] text-xs font-semibold flex items-center gap-1.5 shadow-md transition-all active:scale-95"
          >
            <span>{t.investigateWithCrocol}</span>
            <ArrowRight className="w-3.5 h-3.5 text-[#D9B36C]" />
          </button>
        </div>
      </div>
    </div>
  );
};
