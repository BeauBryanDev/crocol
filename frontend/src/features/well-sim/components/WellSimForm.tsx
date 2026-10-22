import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Gauge, Loader2, MessageSquareText, Play, RotateCcw, SlidersHorizontal, X } from 'lucide-react';
import { useLanguage } from '../../../i18n/useLanguage';
import { ApiError } from '../../../api/apiClient';
import { WellDefaultsResponse, WellLimits, WellParams } from '../../../types/api.types';
import { getWellDefaults, runWell, sweepWell } from '../services/wellSimService';
import { useWellSimStore } from '../store/wellSimStore';
import { buildRequest, Choices, choicesFrom, errorText, FieldError, SECTIONS, SectionSpec, valuesFrom } from '../fields';
import { FieldRow, Section, Segmented } from './FormParts';

type Busy = 'run' | 'sweep' | null;

interface WellSimFormProps {
  onAsk: (question: string, well: WellParams, contextLabel: string) => void;
}

const describe = (exc: unknown, retryIn: string, seconds: string): string => {
  if (exc instanceof ApiError) {
    return exc.retryAfterS ? `${exc.message}. ${retryIn} ${exc.retryAfterS} ${seconds}.` : exc.message;
  }
  return exc instanceof Error ? exc.message : String(exc);
};

export const WellSimForm: React.FC<WellSimFormProps> = ({ onAsk }) => {
  const { t } = useLanguage();
  const { values, choices, openSections, setForm, setValue, setChoice, toggleSection, setFormOpen, setRun, setSweep } =
    useWellSimStore();
  const [defaults, setDefaults] = useState<WellDefaultsResponse | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [errors, setErrors] = useState<Record<string, FieldError>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadDefaults = useCallback(async () => {
    setLoadFailed(false);
    try {
      const loaded = await getWellDefaults();
      setDefaults(loaded);
      if (!useWellSimStore.getState().choices) {
        setForm(valuesFrom(loaded.well, loaded.options), choicesFrom(loaded.well, loaded.options));
      }
    } catch {
      setLoadFailed(true);
    }
  }, [setForm]);

  useEffect(() => {
    loadDefaults();
    return () => abortRef.current?.abort();
  }, [loadDefaults]);

  const resetForm = () => {
    if (!defaults || !window.confirm(t.wsResetConfirm)) return;
    setForm(valuesFrom(defaults.well, defaults.options), choicesFrom(defaults.well, defaults.options));
    setErrors({});
    setMessage(null);
  };

  const validated = () => {
    if (!choices) return null;
    const built = buildRequest(values, choices);
    setErrors(built.errors);
    if (Object.keys(built.errors).length) {
      setMessage(t.wsFixErrors);
      return null;
    }
    setMessage(null);
    return built;
  };

  const submit = async (kind: 'run' | 'sweep') => {
    const built = validated();
    if (!built || busy) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(kind);
    try {
      if (kind === 'run') setRun(await runWell(built.well, controller.signal));
      else setSweep(await sweepWell(built.well, built.options, controller.signal));
    } catch (exc) {
      if (!(exc instanceof DOMException && exc.name === 'AbortError')) {
        setMessage(describe(exc, t.wsRetryIn, t.wsSeconds));
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setBusy(null);
    }
  };

  const ask = () => {
    const built = validated();
    if (built) onAsk(t.wsAskQuestion, built.well, t.wsAskContext);
  };

  const choiceControls = (section: SectionSpec, current: Choices) => {
    const disabled = busy !== null;
    if (section.id === 'well') {
      return (
        <Segmented label={t.wsWellMode} value={current.well_mode} disabled={disabled}
          options={[{ value: 'rate', label: t.wsModeRate }, { value: 'bhp', label: t.wsModeBhp }]}
          onChange={(v) => setChoice('well_mode', v)} />
      );
    }
    if (section.id === 'time') {
      return (
        <Segmented label={t.wsDtMode} value={current.dt_mode} disabled={disabled}
          options={[{ value: 'geometric', label: t.wsDtGeometric }, { value: 'uniform', label: t.wsDtUniform }]}
          onChange={(v) => setChoice('dt_mode', v)} />
      );
    }
    if (section.id === 'sweep') {
      return (
        <Segmented label={t.wsControls} value={current.controls} disabled={disabled}
          options={[
            { value: 'both', label: t.wsControlsBoth },
            { value: 'rate', label: t.wsModeRate },
            { value: 'bhp', label: t.wsModeBhp }
          ]}
          onChange={(v) => setChoice('controls', v)} />
      );
    }
    return null;
  };

  const limitsLine = (limits: WellLimits) =>
    `${t.wsLimitsGrid} ${limits.max_nr}×${limits.max_nz} · ${limits.max_nt} ${t.wsLimitsSteps} · ` +
    `${limits.runs_per_minute} ${t.wsLimitsRuns} · ${limits.sweeps_per_day} ${t.wsLimitsSweeps}`;

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-2xl">
      <div className="shrink-0 mb-1.5 pb-1.5 border-b border-[#F2E8D5]/30 flex items-start gap-2">
        <Gauge className="w-4 h-4 mt-0.5 text-[#D9B36C] shrink-0" />
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-bold tracking-tight text-[#F2E8D5] font-serif-academic">{t.wsTitle}</h2>
          <p className="text-[9.5px] text-[#D9B36C]/75">{t.wsSubtitle}</p>
        </div>
        <button type="button" onClick={resetForm} disabled={!defaults || busy !== null} title={t.wsReset} aria-label={t.wsReset}
          className="p-1 rounded-xs text-[#D9B36C] hover:text-[#F2E8D5] disabled:opacity-40">
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        <button type="button" onClick={() => setFormOpen(false)} title={t.wsClose} aria-label={t.wsClose}
          className="p-1 rounded-xs text-[#D9B36C] hover:text-[#F2E8D5]">
          <X className="w-4 h-4" />
        </button>
      </div>

      {!choices ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-[11px] text-[#F2E8D5]/80">
          {loadFailed ? (
            <>
              <p>{t.wsLoadFailed}</p>
              <button type="button" onClick={loadDefaults} className="px-2 py-0.5 rounded-xs border border-[#D9B36C] text-[#D9B36C]">
                {t.wsRetry}
              </button>
            </>
          ) : (
            <p className="flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" />{t.wsLoading}</p>
          )}
        </div>
      ) : (
        <form className="flex-1 min-h-0 overflow-y-auto pr-1" onSubmit={(e) => { e.preventDefault(); submit('run'); }} noValidate>
          {SECTIONS.map((section) => {
            const open = openSections[section.id] ?? section.openByDefault;
            return (
              <Section key={section.id} title={t[section.title]} open={open} onToggle={() => toggleSection(section.id, !open)}>
                {choiceControls(section, choices)}
                {section.fields
                  .filter((field) => !field.visible || field.visible(choices))
                  .map((field) => (
                    <FieldRow key={field.key} field={field} label={t[field.label]} value={values[field.key] ?? ''}
                      error={errors[field.key] ? errorText(errors[field.key], t) : undefined}
                      disabled={busy !== null} onChange={(v) => setValue(field.key, v)} />
                  ))}
                {section.id === 'constraints' && (
                  <label className="flex items-center gap-1.5 py-1 text-[10.5px] text-[#F2E8D5]/90 cursor-pointer select-none">
                    <input type="checkbox" checked={choices.enforce_pb} disabled={busy !== null}
                      onChange={(e) => setChoice('enforce_pb', e.target.checked)} className="accent-[#2F7D32]" />
                    {t.wsEnforcePb}
                  </label>
                )}
              </Section>
            );
          })}
        </form>
      )}

      <div className="shrink-0 pt-2 mt-1 border-t border-[#F2E8D5]/25 space-y-1.5">
        {message && <p role="alert" className="text-[10px] text-[#e57373]">{message}</p>}
        <div className="flex flex-wrap gap-1.5">
          <button type="button" onClick={() => submit('run')} disabled={!choices || busy !== null}
            className="flex-1 min-w-[72px] px-2 py-1 rounded-md bg-[#2F7D32] text-[#F2E8D5] text-[11px] font-bold flex items-center justify-center gap-1 disabled:opacity-40">
            {busy === 'run' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            {busy === 'run' ? t.wsRunning : t.wsRun}
          </button>
          <button type="button" onClick={() => submit('sweep')} disabled={!choices || busy !== null}
            className="flex-1 min-w-[72px] px-2 py-1 rounded-md bg-[#D9B36C] text-[#24180F] text-[11px] font-bold flex items-center justify-center gap-1 disabled:opacity-40">
            {busy === 'sweep' ? <Loader2 className="w-3 h-3 animate-spin" /> : <SlidersHorizontal className="w-3 h-3" />}
            {busy === 'sweep' ? t.wsSweeping : t.wsSweep}
          </button>
          <button type="button" onClick={ask} disabled={!choices || busy !== null}
            className="flex-1 min-w-[96px] px-2 py-1 rounded-md border border-[#F2E8D5] text-[#F2E8D5] text-[11px] font-bold flex items-center justify-center gap-1 hover:bg-[#2F7D32] disabled:opacity-40">
            <MessageSquareText className="w-3 h-3" />
            {t.wsAsk}
          </button>
        </div>
        {defaults && <p className="text-[9px] text-[#F2E8D5]/55">{limitsLine(defaults.limits)}</p>}
      </div>
    </div>
  );
};
