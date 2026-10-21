import { ApiError, request } from './apiClient';
import { EntityKind, EntityResponse } from '../types/api.types';

const UNIT_KINDS: EntityKind[] = ['formation', 'group', 'member'];

const fetchCard = async (name: string, kind: EntityKind | undefined, signal?: AbortSignal) => {
  const params = new URLSearchParams({ name });
  if (kind) params.set('kind', kind);
  try {
    return await request<EntityResponse>(`/graph/entity?${params.toString()}`, { signal });
  } catch (exc) {
    if (exc instanceof ApiError && exc.status === 404) return null;
    throw exc;
  }
};

// Try each kind in order; only fall back to any kind when allowed, so a
// unit name such as Girón never resolves to the municipality.
export const getEntity = async (
  name: string,
  kinds: EntityKind[],
  anyKind: boolean,
  signal?: AbortSignal
): Promise<EntityResponse | null> => {
  for (const kind of kinds) {
    const card = await fetchCard(name, kind, signal);
    if (card) return card;
  }
  return anyKind ? fetchCard(name, undefined, signal) : null;
};

// "Mesa Formation" -> Mesa; "Noreán / Girón formations" -> Girón.
export const unitQuery = (englishName: string): { name: string; kinds: EntityKind[]; anyKind: boolean } => {
  const found = /^(.*?)\s+(formations?|groups?|members?)$/i.exec(englishName.trim());
  const base = (found ? found[1] : englishName).split('/').pop()!.trim();
  const word = found?.[2].toLowerCase() ?? '';
  const hinted: EntityKind = word.startsWith('group') ? 'group' : word.startsWith('member') ? 'member' : 'formation';
  const kinds = [hinted, ...UNIT_KINDS.filter((kind) => kind !== hinted)];
  return { name: base, kinds, anyKind: false };
};
