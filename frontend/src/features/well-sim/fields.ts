import { translations } from '../../i18n/translations';
import { WellControl, WellParams, WellSweepOptions } from '../../types/api.types';

type Strings = (typeof translations)['en'];

// Bounds mirror WellParams / WellSweepOptions in src/crocol/app/schemas.py;
// the backend re-checks everything, these only give early feedback.
interface Rule {
  min?: number;
  max?: number;
  minExclusive?: boolean;
  maxExclusive?: boolean;
  integer?: boolean;
  optional?: boolean;
}

export type Choices = {
  well_mode: WellParams['well_mode'];
  dt_mode: WellParams['dt_mode'];
  controls: 'both' | WellControl;
  enforce_pb: boolean;
};

export interface FieldSpec {
  key: string;
  label: keyof Strings;
  unit: string;
  rule: Rule;
  target: 'well' | 'options';
  visible?: (choices: Choices) => boolean;
}

export type SectionId = 'geometry' | 'rock' | 'oil' | 'well' | 'constraints' | 'time' | 'sweep';

export interface SectionSpec {
  id: SectionId;
  title: keyof Strings;
  openByDefault: boolean;
  fields: FieldSpec[];
}

const POSITIVE: Rule = { min: 0, minExclusive: true };
const NON_NEGATIVE: Rule = { min: 0 };
const OPTIONAL_POSITIVE: Rule = { ...POSITIVE, optional: true };
const MAX_RAW_LENGTH = 24;

const well = (key: string, label: keyof Strings, unit: string, rule: Rule, visible?: FieldSpec['visible']): FieldSpec => ({
  key, label, unit, rule, target: 'well', visible
});
const option = (key: string, label: keyof Strings, unit: string, rule: Rule): FieldSpec => ({
  key, label, unit, rule, target: 'options'
});

export const SECTIONS: SectionSpec[] = [
  {
    id: 'geometry', title: 'wsSecGeometry', openByDefault: true, fields: [
      well('rw', 'wsRw', 'ft', POSITIVE),
      well('re', 'wsRe', 'ft', POSITIVE),
      well('h', 'wsH', 'ft', POSITIVE),
      well('Nr', 'wsNr', '', { min: 3, max: 50, integer: true }),
      well('Nz', 'wsNz', '', { min: 1, max: 20, integer: true })
    ]
  },
  {
    id: 'rock', title: 'wsSecRock', openByDefault: true, fields: [
      well('kh', 'wsKh', 'md', POSITIVE),
      well('kv_kh', 'wsKvKh', '–', { ...POSITIVE, max: 1 }),
      well('phi', 'wsPhi', 'frac', { ...POSITIVE, max: 1, maxExclusive: true }),
      well('cf', 'wsCf', '1/psi', NON_NEGATIVE),
      well('pi', 'wsPi', 'psi', POSITIVE)
    ]
  },
  {
    id: 'oil', title: 'wsSecOil', openByDefault: true, fields: [
      well('pb', 'wsPb', 'psi', POSITIVE),
      well('mu', 'wsMu', 'cP', POSITIVE),
      well('Bo', 'wsBo', 'rb/STB', POSITIVE),
      well('co', 'wsCo', '1/psi', NON_NEGATIVE),
      well('rho', 'wsRho', 'lb/ft³', POSITIVE),
      well('kro', 'wsKro', '–', { ...POSITIVE, max: 1 })
    ]
  },
  {
    id: 'well', title: 'wsSecWell', openByDefault: true, fields: [
      well('skin', 'wsSkin', '–', { min: -6, max: 100 }),
      well('perf_top', 'wsPerfTop', 'ft', NON_NEGATIVE),
      well('perf_bot', 'wsPerfBot', 'ft', OPTIONAL_POSITIVE),
      well('q', 'wsQ', 'STB/d', POSITIVE, (c) => c.well_mode === 'rate'),
      well('pwf', 'wsPwf', 'psi', POSITIVE, (c) => c.well_mode === 'bhp')
    ]
  },
  {
    id: 'constraints', title: 'wsSecConstraints', openByDefault: true, fields: [
      well('pwf_min', 'wsPwfMin', 'psi', OPTIONAL_POSITIVE),
      well('max_drawdown', 'wsMaxDrawdown', 'psi', OPTIONAL_POSITIVE),
      well('q_max', 'wsQMax', 'STB/d', OPTIONAL_POSITIVE),
      well('q_abandon', 'wsQAbandon', 'STB/d', OPTIONAL_POSITIVE)
    ]
  },
  {
    id: 'time', title: 'wsSecTime', openByDefault: false, fields: [
      well('T', 'wsT', 'd', { ...POSITIVE, max: 36500 }),
      well('Nt', 'wsNt', '', { min: 1, max: 365, integer: true }),
      well('dt0', 'wsDt0', 'd', POSITIVE, (c) => c.dt_mode === 'geometric')
    ]
  },
  {
    id: 'sweep', title: 'wsSecSweep', openByDefault: false, fields: [
      option('n_rate', 'wsNRate', '', { min: 3, max: 12, integer: true }),
      option('n_bhp', 'wsNBhp', '', { min: 3, max: 10, integer: true }),
      option('rate_min', 'wsRateMin', 'STB/d', OPTIONAL_POSITIVE),
      option('rate_max', 'wsRateMax', 'STB/d', OPTIONAL_POSITIVE),
      option('tolerance', 'wsTolerance', 'frac', { ...POSITIVE, max: 0.1 }),
      option('refine_rounds', 'wsRefine', '', { min: 0, max: 3, integer: true }),
      option('discount_rate', 'wsDiscount', 'frac/yr', { min: 0, max: 1 })
    ]
  }
];

export const ALL_FIELDS: FieldSpec[] = SECTIONS.flatMap((s) => s.fields);

export type FieldError =
  | { kind: 'required' | 'number' | 'integer' }
  | { kind: 'min' | 'max'; bound: number; strict: boolean };

export const parseField = (raw: string, rule: Rule): { value: number | null; error: FieldError | null } => {
  const text = raw.trim();
  if (text === '') {
    return rule.optional ? { value: null, error: null } : { value: null, error: { kind: 'required' } };
  }
  const value = text.length > MAX_RAW_LENGTH ? NaN : Number(text);
  if (!Number.isFinite(value)) return { value: null, error: { kind: 'number' } };
  if (rule.integer && !Number.isInteger(value)) return { value: null, error: { kind: 'integer' } };
  if (rule.min !== undefined && (rule.minExclusive ? value <= rule.min : value < rule.min)) {
    return { value: null, error: { kind: 'min', bound: rule.min, strict: Boolean(rule.minExclusive) } };
  }
  if (rule.max !== undefined && (rule.maxExclusive ? value >= rule.max : value > rule.max)) {
    return { value: null, error: { kind: 'max', bound: rule.max, strict: Boolean(rule.maxExclusive) } };
  }
  return { value, error: null };
};

export const errorText = (error: FieldError, t: Strings): string => {
  switch (error.kind) {
    case 'required':
      return t.wsErrRequired;
    case 'number':
      return t.wsErrNumber;
    case 'integer':
      return t.wsErrInteger;
    case 'min':
      return `${error.strict ? t.wsErrAbove : t.wsErrAtLeast} ${error.bound}`;
    case 'max':
      return `${error.strict ? t.wsErrBelow : t.wsErrAtMost} ${error.bound}`;
  }
};

export interface BuiltRequest {
  well: WellParams;
  options: WellSweepOptions;
  errors: Record<string, FieldError>;
}

const controlsOf = (choice: Choices['controls']): WellControl[] => (choice === 'both' ? ['rate', 'bhp'] : [choice]);

// Only finite numbers, nulls, booleans and the fixed choice strings leave
// the browser: free text never reaches the simulator.
export const buildRequest = (values: Record<string, string>, choices: Choices): BuiltRequest => {
  const errors: Record<string, FieldError> = {};
  const well: Record<string, unknown> = {
    well_mode: choices.well_mode,
    dt_mode: choices.dt_mode,
    enforce_pb: choices.enforce_pb
  };
  const options: Record<string, unknown> = { controls: controlsOf(choices.controls) };

  for (const field of ALL_FIELDS) {
    const target = field.target === 'well' ? well : options;
    if (field.visible && !field.visible(choices)) {
      target[field.key] = null;
      continue;
    }
    const { value, error } = parseField(values[field.key] ?? '', field.rule);
    if (error) errors[field.key] = error;
    target[field.key] = value;
  }
  if (well.dt0 === null) delete well.dt0;
  return { well: well as unknown as WellParams, options: options as unknown as WellSweepOptions, errors };
};

const asText = (value: unknown): string => (typeof value === 'number' && Number.isFinite(value) ? String(value) : '');

export const valuesFrom = (wellDefaults: WellParams, optionDefaults: WellSweepOptions): Record<string, string> => {
  const values: Record<string, string> = {};
  for (const field of ALL_FIELDS) {
    const source = (field.target === 'well' ? wellDefaults : optionDefaults) as unknown as Record<string, unknown>;
    values[field.key] = asText(source[field.key]);
  }
  return values;
};

export const choicesFrom = (wellDefaults: WellParams, optionDefaults: WellSweepOptions): Choices => ({
  well_mode: wellDefaults.well_mode,
  dt_mode: wellDefaults.dt_mode,
  enforce_pb: wellDefaults.enforce_pb,
  controls: optionDefaults.controls.length === 2 ? 'both' : optionDefaults.controls[0]
});
