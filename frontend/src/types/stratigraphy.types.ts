export type GeologicalPeriodId =
  | 'quaternary'
  | 'neogene'
  | 'paleogene'
  | 'cretaceous'
  | 'jurassic'
  | 'triassic'
  | 'permian'
  | 'pre-mesozoic';

export type LithologyType =
  | 'sandstone'
  | 'shale'
  | 'limestone'
  | 'conglomerate'
  | 'evaporite'
  | 'volcanic'
  | 'mudstone'
  | 'coal'
  | 'basement';

export interface GeologicalPeriodMeta {
  id: GeologicalPeriodId;
  name: { en: string; es: string };
  color: string;
  textColor?: string;
  order: number;
}

export interface GeologicalFormation {
  id: string;
  name: string;
  displayName: {
    en: string;
    es: string;
  };
  periodId: GeologicalPeriodId;
  epochOrAge: {
    en: string;
    es: string;
  };
  lithologies: LithologyType[];
  lithologyText: {
    en: string;
    es: string;
  };
  facies: {
    en: string;
    es: string;
  };
  description: {
    en: string;
    es: string;
  };
  members?: string[];
  basinIds?: string[];
  sourceIds: string[];
  validationStatus: 'unverified' | 'pending_review' | 'validated';
  petroleumSignificance?: {
    en: string;
    es: string;
  };
}
