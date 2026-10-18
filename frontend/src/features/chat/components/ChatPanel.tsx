import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { ChatMessage } from '../../../types/chat.types';
import { MetaLimits } from '../../../types/api.types';
import { ApiError, getMeta } from '../../../api/apiClient';
import { DEFAULT_IMAGE_MAX_BYTES, DEFAULT_QUESTION_MAX_CHARS, streamAnswer } from '../services/chatService';
import { MessageBubble } from './MessageBubble';
import { QuickActions } from './QuickActions';
import { ChatComposer } from './ChatComposer';
import { GeologicalFormation } from '../../../types/stratigraphy.types';
import { translations } from '../../../i18n/translations';
import { Bot } from 'lucide-react';

interface ChatPanelProps {
  investigatingFormation?: GeologicalFormation | null;
  onClearInvestigatingFormation?: () => void;
  pendingQuestion?: string | null;
  onClearPendingQuestion?: () => void;
}

type Strings = (typeof translations)['en'];

const clock = (): string => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

const greeting = (t: Strings): ChatMessage => ({
  id: 'greeting',
  sender: 'assistant',
  content: t.chatGreeting,
  timestamp: clock()
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
  onClearPendingQuestion
}) => {
  const { language, t } = useLanguage();
  const [messages, setMessages] = useState<ChatMessage[]>(() => [greeting(t)]);
  const [isLoading, setIsLoading] = useState(false);
  const [limits, setLimits] = useState<MetaLimits | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrls = useRef<string[]>([]);

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

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    setMessages((prev) => (prev.length === 1 && prev[0].id === 'greeting' ? [greeting(t)] : prev));
  }, [t]);

  const updateMessage = (id: string, patch: (msg: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((msg) => (msg.id === id ? patch(msg) : msg)));

  const sendQuestion = useCallback(
    async (text: string, image: File | null, contextLabel?: string) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setIsLoading(true);

      const stamp = Date.now();
      const imageUrl = image ? URL.createObjectURL(image) : undefined;
      if (imageUrl) objectUrls.current.push(imageUrl);
      const replyId = `a-${stamp}`;

      setMessages((prev) => [
        ...prev,
        { id: `u-${stamp}`, sender: 'user', content: text, timestamp: clock(), contextLabel, imageUrl },
        { id: replyId, sender: 'assistant', content: '', timestamp: clock(), pending: true, steps: [] }
      ]);

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const final = await streamAnswer(
          text,
          image,
          (step) => updateMessage(replyId, (msg) => ({ ...msg, steps: [...(msg.steps ?? []), step] })),
          controller.signal
        );
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
    [t]
  );

  useEffect(() => {
    if (!investigatingFormation) return;
    const name = investigatingFormation.displayName[language];
    const prompt =
      language === 'es'
        ? `¿Qué se sabe de la formación ${name} en el VMM y cuál es su potencial petrolífero?`
        : `What is known about the ${name} formation in the VMM and what is its petroleum potential?`;
    sendQuestion(prompt, null, `${t.colFormations}: ${name}`);
    onClearInvestigatingFormation?.();
  }, [investigatingFormation]);

  useEffect(() => {
    if (!pendingQuestion) return;
    sendQuestion(pendingQuestion, null);
    onClearPendingQuestion?.();
  }, [pendingQuestion]);

  return (
    <div className="flex flex-col h-full bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg">
      <div className="mb-2 pb-2 border-b border-[#F2E8D5]/30">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#D9B36C]" />
          <h2 className="text-sm font-bold tracking-tight text-[#F2E8D5] font-serif-academic">{t.chatTitle}</h2>
        </div>
        <p className="text-[11px] text-[#D9B36C]/90 mt-0.5">{t.chatSubtitle}</p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto pr-1 space-y-1" aria-live="polite">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
      </div>

      <QuickActions onActionClick={(prompt) => sendQuestion(prompt, null)} disabled={isLoading} />

      <ChatComposer
        onSendMessage={(text, image) => sendQuestion(text, image)}
        isLoading={isLoading}
        maxChars={limits?.question_max_chars ?? DEFAULT_QUESTION_MAX_CHARS}
        maxImageBytes={limits?.image_max_bytes ?? DEFAULT_IMAGE_MAX_BYTES}
      />
    </div>
  );
};
