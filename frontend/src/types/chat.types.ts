import {
  AnswerStatus,
  Conflict,
  MemoryRecord,
  NodeEvent,
  ProductionSeries,
  UiContext,
  Usage,
  WellParams
} from './api.types';

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
  hadImage?: boolean;
  hadOverlay?: boolean;
  production?: ProductionSeries[];
  hadSimulation?: boolean;
  memory?: MemoryRecord | null;
}

export interface QuickActionItem {
  id: string;
  icon: string;
  title: { en: string; es: string };
  prompt: { en: string; es: string };
}

// A question queued from another panel (map, well simulator) for the chat.
export interface PendingQuestion {
  text: string;
  contextLabel?: string;
  well?: WellParams;
  uiContext?: UiContext;
}
