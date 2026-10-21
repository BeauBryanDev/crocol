import React from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Raw HTML in an answer is escaped (react-markdown's default; no rehype-raw).
const components: Components = {
  h1: ({ children }) => <h3 className="mt-3 mb-1.5 text-[14px] font-bold text-[#F2E8D5] font-serif-academic">{children}</h3>,
  h2: ({ children }) => (
    <h3 className="mt-3 mb-1.5 pb-0.5 text-[13.5px] font-bold text-[#D9B36C] border-b border-[#F2E8D5]/15 font-serif-academic">
      {children}
    </h3>
  ),
  h3: ({ children }) => <h4 className="mt-2.5 mb-1 text-[13px] font-semibold text-[#D9B36C]">{children}</h4>,
  h4: ({ children }) => <h5 className="mt-2 mb-1 text-[12.5px] font-semibold text-[#D9B36C]">{children}</h5>,
  p: ({ children }) => <p className="my-1.5">{children}</p>,
  ul: ({ children }) => <ul className="my-1.5 pl-5 list-disc space-y-1 marker:text-[#D9B36C]">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 pl-5 list-decimal space-y-1 marker:text-[#D9B36C]">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-[#F2E8D5]">{children}</strong>,
  em: ({ children }) => <em className="text-[#F2E8D5]/95">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 pl-3 border-l-2 border-[#D9B36C]/60 text-[#F2E8D5]/85 italic">{children}</blockquote>
  ),
  code: ({ children }) => <code className="px-1 py-0.5 rounded-xs bg-[#18100a] text-[12px] font-mono">{children}</code>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline decoration-[#D9B36C]/60 hover:text-[#D9B36C]">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-md border border-[#F2E8D5]/20">
      <table className="w-full border-collapse text-[11.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-[#18100a] text-[#D9B36C]">{children}</thead>,
  th: ({ children }) => <th className="px-2 py-1 text-left font-semibold border-b border-[#F2E8D5]/20">{children}</th>,
  td: ({ children }) => <td className="px-2 py-1 align-top border-b border-[#F2E8D5]/10">{children}</td>,
  hr: () => <hr className="my-3 border-[#F2E8D5]/15" />
};

export const MarkdownAnswer: React.FC<{ text: string }> = ({ text }) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
    {text}
  </ReactMarkdown>
);
