import { AnswerStatus, Conflict, NodeEvent, Usage } from './api.types';

export type MessageSender = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  sender: MessageSender;
  content: string;
  timestamp: string;
  contextLabel?: string;
  imageUrl?: string;
  pending?: boolean;
  steps?: NodeEvent[];
  status?: AnswerStatus;
  references?: string[];
  caveats?: string[];
  conflicts?: Conflict[];
  overlayWebpB64?: string | null;
  traceId?: string;
  usage?: Usage | null;
  isError?: boolean;
}

export interface QuickActionItem {
  id: string;
  icon: string;
  title: { en: string; es: string };
  prompt: { en: string; es: string };
}
