import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { Paperclip, Send, X } from 'lucide-react';
import { IMAGE_MIME_TYPES, QUESTION_MIN_CHARS } from '../services/chatService';

interface ChatComposerProps {
  onSendMessage: (text: string, image: File | null) => void;
  isLoading?: boolean;
  maxChars: number;
  maxImageBytes: number;
  contextFormationName?: string | null;
  onClearContext?: () => void;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({
  onSendMessage,
  isLoading,
  maxChars,
  maxImageBytes,
  contextFormationName,
  onClearContext
}) => {
  const { t } = useLanguage();
  const [text, setText] = useState('');
  const [image, setImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!image) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  const trimmed = text.trim();
  const canSend = trimmed.length >= QUESTION_MIN_CHARS && !isLoading;

  const clearImage = () => {
    setImage(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setHint(null);
    if (!file) return;
    if (!IMAGE_MIME_TYPES.includes(file.type)) {
      setHint(t.imageFormat);
      clearImage();
      return;
    }
    if (file.size > maxImageBytes) {
      setHint(t.imageTooLarge.replace('{mb}', String(Math.round(maxImageBytes / (1024 * 1024)))));
      clearImage();
      return;
    }
    setImage(file);
  };

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (isLoading) return;
    if (trimmed.length < QUESTION_MIN_CHARS) {
      setHint(t.questionTooShort.replace('{n}', String(QUESTION_MIN_CHARS)));
      return;
    }
    setHint(null);
    onSendMessage(trimmed, image);
    setText('');
    clearImage();
  };

  return (
    <div className="mt-auto pt-2 border-t border-[#F2E8D5]/20">
      {contextFormationName && (
        <div className="mb-2 px-2.5 py-1 rounded-md bg-[#2F7D32]/25 border border-[#2F7D32] flex items-center justify-between text-[11px] text-[#D9B36C]">
          <span className="truncate">
            {t.colFormations}: <strong className="text-[#F2E8D5]">{contextFormationName}</strong>
          </span>
          {onClearContext && (
            <button onClick={onClearContext} className="ml-2 text-xs text-[#F2E8D5]/70 hover:text-[#F2E8D5]">
              ×
            </button>
          )}
        </div>
      )}

      {previewUrl && (
        <div className="mb-2 inline-flex items-center gap-2 px-2 py-1 rounded-md bg-[#18100a] border border-[#F2E8D5]/30">
          <img src={previewUrl} alt="" className="w-10 h-10 rounded-xs object-cover" />
          <span className="text-[10px] text-[#F2E8D5]/80 max-w-[160px] truncate">{image?.name}</span>
          <button
            type="button"
            onClick={clearImage}
            className="text-[#D9B36C] hover:text-[#F2E8D5]"
            title={t.removeImage}
            aria-label={t.removeImage}
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {hint && <p className="mb-1.5 text-[10px] text-[#e57373]">{hint}</p>}

      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept={IMAGE_MIME_TYPES.join(',')}
          onChange={handleFile}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={isLoading}
          className={`p-2 rounded-md bg-[#18100a] border text-[#D9B36C] hover:text-[#F2E8D5] hover:border-[#D9B36C] transition-colors disabled:opacity-50 ${
            image ? 'border-[#2F7D32]' : 'border-[#F2E8D5]/30'
          }`}
          title={t.attachImage}
          aria-label={t.attachImage}
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <div className="relative flex-1">
          <input
            id="crocol-chat-input"
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.chatPlaceholder}
            disabled={isLoading}
            maxLength={maxChars}
            className="w-full px-3.5 py-2 rounded-md bg-[#18100a] border border-[#F2E8D5]/40 text-xs text-[#F2E8D5] placeholder-[#D9B36C]/60 focus:outline-hidden focus:border-[#D9B36C] focus:ring-1 focus:ring-[#D9B36C] transition-all disabled:opacity-60"
          />
        </div>

        <button
          type="submit"
          disabled={!canSend}
          className="p-2.5 rounded-md bg-[#D9B36C] text-[#24180F] hover:bg-[#eed59b] font-bold transition-all shadow-md active:scale-95 disabled:opacity-40 disabled:hover:bg-[#D9B36C] disabled:active:scale-100 flex items-center justify-center"
          title={t.chatSend}
          aria-label={t.chatSend}
        >
          <Send className="w-4 h-4 fill-current" />
        </button>
      </form>
    </div>
  );
};
