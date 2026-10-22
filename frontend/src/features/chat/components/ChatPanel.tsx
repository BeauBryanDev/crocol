import React, { useState, useRef, useEffect, useCallback, useLayoutEffect } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { ChatMessage, PendingQuestion } from '../../../types/chat.types';
import { MemoryRecord, UiContext, WellParams } from '../../../types/api.types';
import { useWellSimStore } from '../../well-sim/store/wellSimStore';
import { useVisionStore } from '../../vision/store/visionStore';
import { MetaLimits } from '../../../types/api.types';
import { ApiError, getMeta } from '../../../api/apiClient';
import { DEFAULT_IMAGE_MAX_BYTES, DEFAULT_QUESTION_MAX_CHARS, streamAnswer } from '../services/chatService';
import { useChatStore } from '../store/chatStore';
import { MessageBubble } from './MessageBubble';
import { QuickActions } from './QuickActions';
import { ChatComposer } from './ChatComposer';
import { GeologicalFormation } from '../../../types/stratigraphy.types';
import { translations } from '../../../i18n/translations';
import { Bot, ArrowDown, Trash2, ChevronDown, ChevronUp, ImagePlus } from 'lucide-react';

interface ChatPanelProps {
  investigatingFormation?: GeologicalFormation | null;
  onClearInvestigatingFormation?: () => void;
  pendingQuestion?: PendingQuestion | null;
  onShowOnMap?: () => void;
  onClearPendingQuestion?: () => void;
}

type Strings = (typeof translations)['en'];

const NEAR_BOTTOM_PX = 120;
const MEMORY_TURNS = 3;

const hasFiles = (e: React.DragEvent): boolean => Array.from(e.dataTransfer.types).includes('Files');

const clock = (): string => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

// Crocol's memory: the signed records of the last finished answers.
const recentMemory = (messages: ChatMessage[]): MemoryRecord[] =>
  messages
    .filter((m) => m.sender === 'assistant' && m.memory)
    .slice(-MEMORY_TURNS)
    .map((m) => m.memory as MemoryRecord);

const greeting = (t: Strings): ChatMessage => ({
  id: 'greeting',
  sender: 'assistant',
  content: t.chatGreeting,
  timestamp: ''
});

const describeError = (exc: unknown, t: Strings): string => {
  if (exc instanceof ApiError) {
    if (exc.status === 0 && exc.message === 'network error') return t.errorNetwork;
    if (exc.status === 429 && exc.retryAfterS !== null && exc.retryAfterS <= 120) {
      return t.errorRateLimited.replace('{s}', String(exc.retryAfterS));
    }
    if (exc.status === 429 && exc.retryAfterS !== null) return t.errorRateLimitedNoWait;
    const ref = exc.requestId ? ` (${exc.requestId.slice(0, 8)})` : '';
    return `${t.errorGeneric}: ${exc.message}${ref}`;
  }
  return t.errorGeneric;
};

export const ChatPanel: React.FC<ChatPanelProps> = ({
  investigatingFormation,
  onClearInvestigatingFormation,
  pendingQuestion,
  onClearPendingQuestion,
  onShowOnMap
}) => {
  const { language, t } = useLanguage();
  const messages = useChatStore((state) => state.messages);
  const addMessages = useChatStore((state) => state.addMessages);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const clearMessages = useChatStore((state) => state.clearMessages);

  const [isLoading, setIsLoading] = useState(false);
  const [limits, setLimits] = useState<MetaLimits | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bubbleRefs = useRef(new Map<string, HTMLDivElement>());
  const atBottomRef = useRef(true);
  const pendingIdRef = useRef<string | null>(null);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrls = useRef<string[]>([]);

  const hasConversation = messages.some((m) => m.sender === 'user');
  const suggestionsOpen = !hasConversation || showSuggestions;

  useEffect(() => {
    const controller = new AbortController();
    getMeta(controller.signal)
      .then((meta) => setLimits(meta.limits))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      objectUrls.current.forEach((url) => URL.revokeObjectURL(url));
    },
    []
  );

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const box = scrollRef.current;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior });
  }, []);

  const handleScroll = () => {
    const box = scrollRef.current;
    if (!box) return;
    const near = box.scrollHeight - box.scrollTop - box.clientHeight < NEAR_BOTTOM_PX;
    atBottomRef.current = near;
    setAtBottom(near);
  };

  // Restored conversations open at the latest message.
  useLayoutEffect(() => {
    scrollToBottom('auto');
  }, [scrollToBottom]);

  // While an answer streams, follow it only if the reader is at the bottom.
  // When it finishes, show its first line, so a long answer reads from the top.
  useEffect(() => {
    const pendingId = pendingIdRef.current;
    if (!pendingId) return;
    const message = messages.find((m) => m.id === pendingId);
    if (message && !message.pending) {
      pendingIdRef.current = null;
      if (atBottomRef.current) {
        bubbleRefs.current.get(pendingId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return;
    }
    if (atBottomRef.current) scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendQuestion = useCallback(
    async (
      text: string,
      image: File | null,
      contextLabel?: string,
      well: WellParams | null = null,
      uiContext: UiContext | null = null
    ) => {
      if (busyRef.current) return;
      const history = recentMemory(useChatStore.getState().messages);
      busyRef.current = true;
      setIsLoading(true);
      setShowSuggestions(false);

      const stamp = Date.now();
      const imageUrl = image ? URL.createObjectURL(image) : undefined;
      if (imageUrl) objectUrls.current.push(imageUrl);
      const replyId = `a-${stamp}`;
      pendingIdRef.current = replyId;
      atBottomRef.current = true;

      addMessages(
        { id: `u-${stamp}`, sender: 'user', content: text, timestamp: clock(), contextLabel, imageUrl },
        { id: replyId, sender: 'assistant', content: '', timestamp: clock(), pending: true, steps: [] }
      );
      requestAnimationFrame(() => scrollToBottom());

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const final = await streamAnswer(
          text,
          image,
          (step) => updateMessage(replyId, (msg) => ({ ...msg, steps: [...(msg.steps ?? []), step] })),
          controller.signal,
          { well, history, uiContext }
        );
        if (final.simulation) useWellSimStore.getState().setSweep(final.simulation);
        if (final.vision) {
          useVisionStore.getState().setResult(replyId, final.vision, imageUrl ?? null, final.overlay_webp_b64);
        }
        updateMessage(replyId, (msg) => ({
          ...msg,
          pending: false,
          content: final.answer,
          status: final.status,
          references: final.references,
          caveats: final.caveats,
          conflicts: final.conflicts,
          overlayWebpB64: final.overlay_webp_b64,
          traceId: final.trace_id,
          usage: final.usage,
          production: final.production ?? [],
          hadSimulation: Boolean(final.simulation),
          memory: final.memory ?? null,
          timestamp: clock()
        }));
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === 'AbortError') return;
        updateMessage(replyId, (msg) => ({
          ...msg,
          pending: false,
          isError: true,
          content: describeError(exc, t),
          timestamp: clock()
        }));
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        busyRef.current = false;
        setIsLoading(false);
      }
    },
    [t, addMessages, updateMessage, scrollToBottom]
  );

  const handleClear = () => {
    if (isLoading || !hasConversation) return;
    if (window.confirm(t.chatClearConfirm)) clearMessages();
  };

  useEffect(() => {
    if (!investigatingFormation) return;
    const name = investigatingFormation.displayName[language];
    const prompt =
      language === 'es'
        ? `¿Qué se sabe de la formación ${name} en el VMM y cuál es su potencial petrolífero?`
        : `What is known about the ${name} formation in the VMM and what is its petroleum potential?`;
    sendQuestion(prompt, null, `${t.colFormations}: ${name}`, null, { formation: name });
    onClearInvestigatingFormation?.();
  }, [investigatingFormation]);

  useEffect(() => {
    if (!pendingQuestion) return;
    sendQuestion(
      pendingQuestion.text,
      null,
      pendingQuestion.contextLabel,
      pendingQuestion.well ?? null,
      pendingQuestion.uiContext ?? null
    );
    onClearPendingQuestion?.();
  }, [pendingQuestion]);

  const [droppedFile, setDroppedFile] = useState<{ file: File; id: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);

  const handleDragEnter = (e: React.DragEvent) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = isLoading ? 'none' : 'copy';
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!hasFiles(e)) return;
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && !isLoading) setDroppedFile({ file, id: Date.now() });
  };

  const shown = [greeting(t), ...messages];

  return (
    <div
      className="relative flex flex-col h-full min-h-0 overflow-hidden bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-2 z-20 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[#D9B36C] bg-[#24180F]/90 text-[#F2E8D5]">
          <ImagePlus className="w-8 h-8 text-[#D9B36C]" />
          <p className="text-xs font-semibold">{isLoading ? t.dropImageBusy : t.dropImage}</p>
          <p className="text-[10.5px] text-[#D9B36C]/90">{t.imageFormatHint}</p>
        </div>
      )}
      <div className="shrink-0 mb-2 pb-2 border-b border-[#F2E8D5]/30 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-[#D9B36C]" />
            <h2 className="text-sm font-bold tracking-tight text-[#F2E8D5] font-serif-academic">{t.chatTitle}</h2>
          </div>
          <p className="text-[11px] text-[#D9B36C]/90 mt-0.5">{t.chatSubtitle}</p>
        </div>
        <button
          type="button"
          onClick={handleClear}
          disabled={isLoading || !hasConversation}
          className="shrink-0 p-1.5 rounded-md text-[#D9B36C]/80 hover:text-[#F2E8D5] hover:bg-[#F2E8D5]/10 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
          title={t.chatClear}
          aria-label={t.chatClear}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div className="relative flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto overscroll-contain pr-1.5 scroll-smooth"
          aria-live="polite"
        >
          {shown.map((msg) => (
            <div
              key={msg.id}
              ref={(node) => {
                if (node) bubbleRefs.current.set(msg.id, node);
                else bubbleRefs.current.delete(msg.id);
              }}
              className="scroll-mt-2"
            >
              <MessageBubble message={msg} onShowOnMap={onShowOnMap} />
            </div>
          ))}
        </div>

        {!atBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom()}
            className="absolute bottom-3 right-3 z-10 flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-[#D9B36C] text-[#24180F] text-[10.5px] font-semibold shadow-lg hover:bg-[#eed59b] transition-colors"
            title={t.jumpToLatest}
            aria-label={t.jumpToLatest}
          >
            <ArrowDown className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{t.jumpToLatest}</span>
          </button>
        )}
      </div>

      <div className="shrink-0">
        {hasConversation && (
          <button
            type="button"
            onClick={() => setShowSuggestions((open) => !open)}
            className="mt-2 flex items-center gap-1 text-[10.5px] text-[#D9B36C]/80 hover:text-[#F2E8D5] transition-colors"
            aria-expanded={suggestionsOpen}
          >
            {suggestionsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>{suggestionsOpen ? t.quickActionsHide : t.quickActionsShow}</span>
          </button>
        )}
        {suggestionsOpen && (
          <QuickActions onActionClick={(prompt) => sendQuestion(prompt, null)} disabled={isLoading} />
        )}

        <ChatComposer
          onSendMessage={(text, image) => sendQuestion(text, image)}
          isLoading={isLoading}
          maxChars={limits?.question_max_chars ?? DEFAULT_QUESTION_MAX_CHARS}
          maxImageBytes={limits?.image_max_bytes ?? DEFAULT_IMAGE_MAX_BYTES}
          droppedFile={droppedFile}
        />
      </div>
    </div>
  );
};
