import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { FieldSpec } from '../fields';

export const FieldRow: React.FC<{
  field: FieldSpec;
  label: string;
  value: string;
  error?: string;
  disabled: boolean;
  onChange: (value: string) => void;
}> = ({ field, label, value, error, disabled, onChange }) => {
  const id = `ws-${field.key}`;
  return (
    <div className="py-0.5">
      <div className="flex items-center gap-1.5">
        <label htmlFor={id} className="flex-1 min-w-0 text-[10.5px] leading-tight text-[#F2E8D5]/90">
          {label}
        </label>
        <input
          id={id}
          type="number"
          inputMode="decimal"
          step="any"
          min={field.rule.min}
          max={field.rule.max}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`w-[84px] shrink-0 px-1.5 py-0.5 rounded-xs bg-[#18100a] border text-[11px] text-right text-[#F2E8D5] focus:outline-hidden focus:border-[#D9B36C] disabled:opacity-50 ${
            error ? 'border-[#e57373]' : 'border-[#F2E8D5]/35'
          }`}
        />
        <span className="w-[46px] shrink-0 text-[9.5px] text-[#D9B36C]/80">{field.unit}</span>
      </div>
      {error && (
        <p id={`${id}-error`} className="text-[9.5px] text-[#e57373] text-right pr-[52px]">
          {error}
        </p>
      )}
    </div>
  );
};

export const Section: React.FC<{
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}> = ({ title, open, onToggle, children }) => (
  <section className="border-b border-[#F2E8D5]/15 pb-1">
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="w-full flex items-center gap-1 py-1 text-[11px] font-bold text-[#D9B36C] hover:text-[#F2E8D5]"
    >
      {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
      <span>{title}</span>
    </button>
    {open && <div className="pl-1">{children}</div>}
  </section>
);

export const Segmented = <T extends string>({
  label,
  value,
  options,
  disabled,
  onChange
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  disabled: boolean;
  onChange: (value: T) => void;
}) => (
  <div className="flex items-center gap-1.5 py-0.5">
    <span className="flex-1 text-[10.5px] text-[#F2E8D5]/90">{label}</span>
    <div className="flex rounded-xs border border-[#F2E8D5]/35 overflow-hidden" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          disabled={disabled}
          onClick={() => onChange(option.value)}
          className={`px-2 py-0.5 text-[10px] font-semibold disabled:opacity-50 ${
            value === option.value ? 'bg-[#2F7D32] text-[#F2E8D5]' : 'text-[#D9B36C] hover:bg-[#F2E8D5]/10'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  </div>
);
