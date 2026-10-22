import React, { useEffect, useState } from 'react';
import { Network, BookOpen, Loader2 } from 'lucide-react';
import { useLanguage } from '../../i18n/useLanguage';
import { Language } from '../../i18n/translations';
import { getEntity } from '../../api/graphService';
import { EntityKind, EntityRelation, EntityResponse } from '../../types/api.types';

interface EntityCardProps {
  name: string;
  kinds?: EntityKind[];
  anyKind?: boolean;
  compact?: boolean;
}

type Phase = 'loading' | 'ready' | 'missing' | 'error';

const REL_LABELS: Record<string, Record<Language, string>> = {
  'in:PART_OF': { es: 'Incluye', en: 'Includes' },
  'out:PART_OF': { es: 'Hace parte de', en: 'Part of' },
  'out:OVERLIES': { es: 'Suprayace a', en: 'Overlies' },
  'in:OVERLIES': { es: 'Infrayace a', en: 'Underlies' },
  'out:EQUIVALENT_OF': { es: 'Equivalente de', en: 'Equivalent of' },
  'in:EQUIVALENT_OF': { es: 'Equivalente de', en: 'Equivalent of' },
  'in:IN_FIELD': { es: 'Pozos del campo', en: 'Wells in field' },
  'out:IN_FIELD': { es: 'Campo', en: 'Field' },
  'out:LOCATED_IN': { es: 'Municipio', en: 'Municipality' },
  'in:LOCATED_IN': { es: 'Pozos en el municipio', en: 'Wells in municipality' },
  'out:OPERATED_BY': { es: 'Operador', en: 'Operator' },
  'in:OPERATED_BY': { es: 'Opera', en: 'Operates' },
  'out:IN_CONTRACT': { es: 'Contrato (ANH)', en: 'Contract (ANH)' },
  'in:IN_CONTRACT': { es: 'Pozos y programas', en: 'Wells and surveys' },
  'out:IN_BASIN': { es: 'Cuenca', en: 'Basin' },
  'in:IN_BASIN': { es: 'Contiene', en: 'Contains' },
  'in:DESCRIBES': { es: 'Descrita en', en: 'Described in' },
  'out:DESCRIBES': { es: 'Describe', en: 'Describes' },
  'out:AUTHORED_BY': { es: 'Autores', en: 'Authors' },
  'in:AUTHORED_BY': { es: 'Autor de', en: 'Author of' },
  'out:PUBLISHED_BY': { es: 'Publicado por', en: 'Published by' },
  'out:ABOUT': { es: 'Temas', en: 'Topics' },
  'in:ABOUT': { es: 'Documentos', en: 'Documents' },
  'in:HOLDS': { es: 'Contratista', en: 'Contractor' },
  'out:HOLDS': { es: 'Titular de', en: 'Holds' },
  'out:COVERS': { es: 'Área', en: 'Area' },
  'in:COVERS': { es: 'Contrato', en: 'Contract' },
  'out:GOVERNED_BY': { es: 'Regido por', en: 'Governed by' },
  'out:DESCRIBED_IN': { es: 'Documento', en: 'Document' }
};
const COMPACT_RELATIONS = 4;
const NAMES_SHOWN = 6;

const relLabel = (relation: EntityRelation, lang: Language) =>
  REL_LABELS[`${relation.direction}:${relation.rel}`]?.[lang] ?? relation.rel;

const RelationRow: React.FC<{ relation: EntityRelation; lang: Language; more: string }> = ({ relation, lang, more }) => {
  const names = relation.names.slice(0, NAMES_SHOWN);
  const extra = relation.total - names.length;
  return (
    <li className="leading-snug">
      <strong className="text-[#D9B36C]">{relLabel(relation, lang)}</strong>
      <span className="text-[#D9B36C]/60"> ({relation.total})</span>: {names.join(', ')}
      {extra > 0 && <span className="text-[#D9B36C]/60"> +{extra} {more}</span>}
    </li>
  );
};

export const EntityCard: React.FC<EntityCardProps> = ({ name, kinds = [], anyKind = true, compact }) => {
  const { language, t } = useLanguage();
  const [card, setCard] = useState<EntityResponse | null>(null);
  const [phase, setPhase] = useState<Phase>('loading');

  useEffect(() => {
    const controller = new AbortController();
    setPhase('loading');
    getEntity(name, kinds, anyKind, controller.signal)
      .then((found) => {
        setCard(found);
        setPhase(found ? 'ready' : 'missing');
      })
      .catch((exc) => {
        if (exc instanceof DOMException && exc.name === 'AbortError') return;
        setPhase('error');
      });
    return () => controller.abort();
  }, [name, kinds.join(','), anyKind]);

  if (phase === 'loading') {
    return (
      <div className="flex items-center gap-1.5 text-[10px] text-[#D9B36C]/80">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>{t.kgLoading}</span>
      </div>
    );
  }
  if (phase !== 'ready' || !card) {
    return <p className="text-[10px] text-[#D9B36C]/70">{phase === 'error' ? t.kgError : t.kgNotFound}</p>;
  }

  const facts = card.relations.filter((r) => r.rel !== 'CO_MENTIONED');
  const coMentions = card.relations.filter((r) => r.rel === 'CO_MENTIONED');
  const age = card.entity.props.age;
  const shownFacts = compact ? facts.slice(0, COMPACT_RELATIONS) : facts;

  return (
    <section className={`rounded-md border border-[#F2E8D5]/25 bg-[#18100a] ${compact ? 'p-1.5 text-[9px]' : 'p-3 text-[10.5px]'} text-[#F2E8D5]/90 space-y-1.5`}>
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[#D9B36C] font-semibold">
          <Network className="w-3 h-3" />
          <span>{t.kgTitle}</span>
        </div>
        <span className="text-[#D9B36C]/60 font-mono">{card.source}</span>
      </header>

      <div>
        <strong className="text-[#F2E8D5]">{card.entity.name}</strong>
        <span className="text-[#D9B36C]/70"> · {card.entity.kind} · {card.entity.mentions} {t.kgMentions}</span>
        {typeof age === 'string' && age && (
          <div className="text-[#D9B36C]/80">{t.kgAge}: {age}</div>
        )}
      </div>

      {shownFacts.length > 0 && (
        <div>
          {!compact && <div className="font-semibold text-[#D9B36C] mb-0.5">{t.kgRelations}</div>}
          <ul className="space-y-0.5">
            {shownFacts.map((relation) => (
              <RelationRow key={`${relation.direction}-${relation.rel}-${relation.kind}`} relation={relation} lang={language} more={t.kgMore} />
            ))}
          </ul>
        </div>
      )}

      {!compact && coMentions.length > 0 && (
        <div>
          <div className="font-semibold text-[#D9B36C] mb-0.5">{t.kgCoMentions}</div>
          <p className="text-[#F2E8D5]/70">
            {coMentions.flatMap((r) => r.names.slice(0, 3)).slice(0, 12).join(', ')}
          </p>
        </div>
      )}

      {!compact && card.documents.length > 0 && (
        <div>
          <div className="flex items-center gap-1 font-semibold text-[#D9B36C] mb-0.5">
            <BookOpen className="w-3 h-3" />
            <span>{t.kgDocuments}</span>
          </div>
          <ul className="space-y-0.5">
            {card.documents.map((doc) => (
              <li key={doc.doc_id} className="leading-snug">
                <span className="text-[#F2E8D5]">{doc.citation}</span>
                <span className="text-[#D9B36C]/60">
                  {' '}· {doc.chunks} {t.kgPassages}
                  {doc.described && ` · ${t.kgDescribed}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};
