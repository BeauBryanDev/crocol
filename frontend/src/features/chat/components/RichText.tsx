import React from 'react';

const INLINE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g;

const renderInline = (text: string, keyPrefix: string): React.ReactNode[] =>
  text.split(INLINE).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key} className="text-[#D9B36C]">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={key} className="px-1 rounded-xs bg-[#18100a]">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return part;
  });

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'para'; lines: string[] }
  | { kind: 'list'; ordered: boolean; items: string[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

const toBlocks = (source: string): Block[] => {
  const blocks: Block[] = [];
  for (const line of source.split('\n')) {
    const last = blocks[blocks.length - 1];
    const heading = HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);
    if (!line.trim()) {
      blocks.push({ kind: 'para', lines: [] });
    } else if (heading) {
      blocks.push({ kind: 'heading', text: heading[1] });
    } else if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const item = (bullet ?? numbered)![1];
      if (last?.kind === 'list' && last.ordered === ordered) last.items.push(item);
      else blocks.push({ kind: 'list', ordered, items: [item] });
    } else if (last?.kind === 'para') {
      last.lines.push(line);
    } else {
      blocks.push({ kind: 'para', lines: [line] });
    }
  }
  return blocks.filter((b) => b.kind !== 'para' || b.lines.length > 0);
};

export const RichText: React.FC<{ text: string }> = ({ text }) => (
  <div className="space-y-1.5">
    {toBlocks(text).map((block, i) => {
      if (block.kind === 'heading') {
        return (
          <p key={i} className="font-bold text-[#D9B36C] text-[12px]">
            {renderInline(block.text, `h${i}`)}
          </p>
        );
      }
      if (block.kind === 'list') {
        const ListTag = block.ordered ? 'ol' : 'ul';
        return (
          <ListTag key={i} className={`pl-4 space-y-0.5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>
            {block.items.map((item, j) => (
              <li key={j}>{renderInline(item, `l${i}-${j}`)}</li>
            ))}
          </ListTag>
        );
      }
      return (
        <p key={i}>
          {block.lines.map((line, j) => (
            <React.Fragment key={j}>
              {j > 0 && <br />}
              {renderInline(line, `p${i}-${j}`)}
            </React.Fragment>
          ))}
        </p>
      );
    })}
  </div>
);
