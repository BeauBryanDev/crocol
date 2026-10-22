import React from 'react';
import { ChatMessage } from '../../../types/chat.types';
import { User,
   BookOpen,
   Layers,
   AlertTriangle,
    Scale,
   Loader2,
   CheckCircle2,
    CircleSlash, 
    CircleAlert, 
    ImageOff,
     Info, 
    ScanSearch } from 'lucide-react';
import { useVisionStore } from '../../vision/store/visionStore';
import { useMapOverlayStore } from '../../map-overlay/store/mapOverlayStore';
import { useLanguage } from '../../../i18n/useLanguage';
import { nodeLabel } from '../services/chatService';
import { MarkdownAnswer } from './MarkdownAnswer';
import crocolAvatar from '../../../assets/Crocol_Avatar.jpg';

interface MessageBubbleProps {
  message: ChatMessage;
  onShowOnMap?: () => void;
}

const STEP_ICON: Record<string, React.ReactNode> = {
  ok: <CheckCircle2 className="w-3 h-3 text-[#2F7D32]" />,
  skipped: <CircleSlash className="w-3 h-3 text-[#D9B36C]/60" />,
  fallback: <CircleAlert className="w-3 h-3 text-[#D9B36C]" />,
  timeout: <CircleAlert className="w-3 h-3 text-[#e53935]" />,
  error: <CircleAlert className="w-3 h-3 text-[#e53935]" />
};

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onShowOnMap }) => {
  const { language, t } = useLanguage();
  const ownsVision = useVisionStore((state) => state.messageId === message.id);
  const openOverlay = useMapOverlayStore((state) => state.open);
  const isAssistant = message.sender === 'assistant';
  const steps = message.steps ?? [];

  const statusBadge =
    message.status === 'partial'
      ? t.statusPartial
      : message.status === 'abstained'
      ? t.statusAbstained
      : message.status === 'error'
      ? t.statusError
      : null;

  return (
    <div className="flex items-start gap-2.5 my-2.5">
      <div className="shrink-0 mt-0.5">
        {isAssistant ? (
          <div className="w-9 h-9 rounded-full overflow-hidden border border-[#D9B36C] bg-[#1a110a] shadow-md flex items-center justify-center">
            <img
              src={crocolAvatar}
              alt="Crocol"
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          </div>
        ) : (
          <div className="w-9 h-9 rounded-full bg-[#3e2b1d] border border-[#F2E8D5]/60 flex items-center justify-center text-[#F2E8D5] shadow-xs">
            <User className="w-5 h-5 text-[#D9B36C]" />
          </div>
        )}
      </div>

      <div className={`flex-1 min-w-0 ${isAssistant ? 'max-w-[88%]' : 'max-w-[92%]'}`}>
        <div
          className={`rounded-lg border leading-relaxed transition-all shadow-sm ${
            message.isError
              ? 'p-3 text-xs bg-[#2a120c] border-[#e53935]/60 text-[#F2E8D5]'
              : isAssistant
              ? 'p-3 text-xs bg-[#1e130a] border-[#F2E8D5]/30 text-[#F2E8D5]'
              : 'px-4 py-3.5 text-sm bg-[#2b1c10] border-[#D9B36C]/50 text-[#F2E8D5]'
          }`}
        >
          {message.contextLabel && (
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 mb-2 rounded-xs bg-[#2F7D32]/30 border border-[#2F7D32] text-[10px] text-[#D9B36C]">
              <Layers className="w-3 h-3 text-[#D9B36C]" />
              <span>{message.contextLabel}</span>
            </div>
          )}

          {statusBadge && (
            <div className="inline-flex items-center gap-1 px-2 py-0.5 mb-2 ml-1 rounded-xs bg-[#D9B36C]/15 border border-[#D9B36C]/60 text-[10px] text-[#D9B36C]">
              <AlertTriangle className="w-3 h-3" />
              <span>{statusBadge}</span>
            </div>
          )}

          {message.imageUrl ? (
            <img
              src={message.imageUrl}
              alt=""
              className="mb-2 max-h-40 rounded-md border border-[#F2E8D5]/30 object-contain"
            />
          ) : (
            message.hadImage && (
              <div className="mb-2 inline-flex items-center gap-1.5 text-[10.5px] text-[#D9B36C]/80">
                <ImageOff className="w-3.5 h-3.5" />
                <span>{t.imageNotSaved}</span>
              </div>
            )
          )}

          {message.pending ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-[11px] text-[#D9B36C]">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>
                  {steps.length ? nodeLabel(steps[steps.length - 1].node, language) : t.consultingDatabase}
                </span>
              </div>
            </div>
          ) : isAssistant ? (
            <div className="font-sans text-[13px] leading-[1.65] break-words">
              <MarkdownAnswer text={message.content} />
            </div>
          ) : (
            <div className="w-full min-w-0 whitespace-pre-wrap wrap-break-word font-sans text-sm leading-relaxed">
              {message.content}
            </div>
          )}

          {message.overlayWebpB64 && (
            <figure className="mt-2.5">
              <img
                src={`data:image/webp;base64,${message.overlayWebpB64}`}
                alt={t.overlayTitle}
                className="max-h-64 w-full rounded-md border border-[#F2E8D5]/30 object-contain bg-[#18100a]"
              />
              <figcaption className="mt-1 text-[10px] text-[#D9B36C]/80">{t.overlayTitle}</figcaption>
            </figure>
          )}
          {ownsVision && (
            <button
              type="button"
              onClick={() => {
                openOverlay('vision');
                onShowOnMap?.();
              }}
              className="mt-1.5 flex items-center gap-1 px-2 py-0.5 rounded-md border border-[#D9B36C]/70 text-[10.5px] font-semibold text-[#D9B36C] hover:bg-[#2F7D32] hover:text-[#F2E8D5]"
            >
              <ScanSearch className="w-3 h-3" />
              {t.cvShowOnMap}
            </button>
          )}
          {!message.overlayWebpB64 && message.hadOverlay && (
            <p className="mt-2 text-[10.5px] text-[#D9B36C]/70 italic">{t.overlayNotSaved}</p>
          )}

          {message.conflicts && message.conflicts.length > 0 && (
            <div className="mt-2.5 pt-2 border-t border-[#F2E8D5]/20 text-[10px]">
              <div className="flex items-center gap-1 text-[#D9B36C] font-semibold mb-1">
                <Scale className="w-3 h-3" />
                <span>{t.conflictsTitle}</span>
              </div>
              <ul className="space-y-1.5">
                {message.conflicts.map((conflict, i) => (
                  <li key={i} className="text-[#F2E8D5]/85">
                    <strong className="text-[#D9B36C]">
                      {conflict.entity} · {conflict.property.toUpperCase()}
                    </strong>
                    {!conflict.comparable && <span className="text-[#D9B36C]/70"> ({t.notComparable})</span>}
                    <ul className="pl-3 mt-0.5 space-y-0.5">
                      {conflict.sides.map((side, j) => (
                        <li key={j}>
                          {side.value} {side.unit} — {side.citation}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {message.references && message.references.length > 0 && (
            <div className="mt-2.5 pt-2 border-t border-[#F2E8D5]/20 text-[10px]">
              <div className="flex items-center gap-1 text-[#D9B36C] font-semibold mb-1">
                <BookOpen className="w-3 h-3" />
                <span>{t.sourceReferences}</span>
              </div>
              <ul className="space-y-1">
                {message.references.map((ref, i) => (
                  <li key={i} className="text-[#F2E8D5]/80 flex items-start gap-1">
                    <span className="text-[#D9B36C]">•</span>
                    <span className="break-words">{ref}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {message.caveats && message.caveats.length > 0 && (
            <details className="mt-2 text-[10px] text-[#D9B36C]/70">
              <summary className="cursor-pointer select-none inline-flex items-center gap-1 hover:text-[#D9B36C]">
                <Info className="w-3 h-3" />
                <span>
                  {t.caveatsTitle} ({message.caveats.length})
                </span>
              </summary>
              <ul className="mt-1 space-y-0.5 list-disc pl-4 text-[#F2E8D5]/65">
                {message.caveats.map((caveat, i) => (
                  <li key={i}>{caveat}</li>
                ))}
              </ul>
            </details>
          )}

          {!message.pending && steps.length > 0 && (
            <details className="mt-2 text-[10px] text-[#D9B36C]/80">
              <summary className="cursor-pointer select-none">
                {t.stepsTitle} ({steps.length})
              </summary>
              <ol className="mt-1 space-y-0.5">
                {steps.map((step, i) => (
                  <li key={i} className="flex items-center gap-1.5">
                    {STEP_ICON[step.status] ?? STEP_ICON.ok}
                    <span className="text-[#F2E8D5]/80">{nodeLabel(step.node, language)}</span>
                    <span className="ml-auto font-mono">{(step.duration_ms / 1000).toFixed(1)} s</span>
                  </li>
                ))}
              </ol>
            </details>
          )}

          <div className="flex items-center justify-between gap-2 mt-1.5 text-[9.5px] text-[#D9B36C]/70">
            <span className="truncate font-mono">
              {message.traceId && `${t.traceLabel} ${message.traceId.slice(0, 8)}`}
              {message.usage &&
                ` · ${t.usageLabel
                  .replace('{calls}', String(message.usage.llm_calls))
                  .replace('{tokens}', message.usage.tokens.toLocaleString())}`}
            </span>
            <span className="shrink-0">{message.timestamp}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
