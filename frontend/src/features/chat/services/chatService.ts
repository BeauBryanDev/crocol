import { ApiError, apiUrl, errorFromResponse } from '../../../api/apiClient';
import { ChatResponse, NodeEvent } from '../../../types/api.types';
import { Language } from '../../../i18n/translations';

export const QUESTION_MIN_CHARS = 3;
export const DEFAULT_QUESTION_MAX_CHARS = 2000;
export const DEFAULT_IMAGE_MAX_BYTES = 10 * 1024 * 1024;
export const IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export const NODE_LABELS: Record<string, Record<Language, string>> = {
  analyze: { es: 'Analizando la pregunta', en: 'Analyzing the question' },
  plan: { es: 'Planeando la investigación', en: 'Planning the research' },
  investigate: { es: 'Investigando una subpregunta', en: 'Investigating a sub-question' },
  merge: { es: 'Uniendo la evidencia', en: 'Merging the evidence' },
  retrieve_text: { es: 'Buscando en el corpus', en: 'Searching the corpus' },
  retrieve_spatial: { es: 'Consultando datos espaciales ANH', en: 'Querying ANH spatial data' },
  retrieve_graph: { es: 'Consultando el grafo', en: 'Querying the graph' },
  retrieve_vision: { es: 'Analizando la imagen', en: 'Analyzing the image' },
  fuse: { es: 'Fusionando resultados', en: 'Fusing results' },
  rerank: { es: 'Reordenando pasajes', en: 'Reranking passages' },
  grade: { es: 'Evaluando la evidencia', en: 'Grading the evidence' },
  rewrite: { es: 'Reformulando la búsqueda', en: 'Rewriting the search' },
  conflict_check: { es: 'Buscando contradicciones', en: 'Checking for conflicts' },
  synthesize: { es: 'Redactando la respuesta', en: 'Writing the answer' },
  verify: { es: 'Verificando afirmaciones', en: 'Verifying claims' },
  revise: { es: 'Corrigiendo la respuesta', en: 'Revising the answer' },
  abstain: { es: 'Sin evidencia suficiente', en: 'Not enough evidence' },
  finalize: { es: 'Preparando citas', en: 'Preparing citations' }
};

export const nodeLabel = (node: string, lang: Language): string => NODE_LABELS[node]?.[lang] ?? node;

const parseFrame = (frame: string): { event: string; data: string } | null => {
  let event = 'message';
  const data: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue;
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
  }
  return data.length ? { event, data: data.join('\n') } : null;
};

const buildRequest = (question: string, image: File | null, signal: AbortSignal): [string, RequestInit] => {
  if (image) {
    const form = new FormData();
    form.append('question', question);
    form.append('image', image);
    return [apiUrl('/image/stream'), { method: 'POST', body: form, signal }];
  }
  return [
    apiUrl('/chat/stream'),
    {
      method: 'POST',
      body: JSON.stringify({ question }),
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      signal
    }
  ];
};

export const streamAnswer = async (
  question: string,
  image: File | null,
  onNode: (event: NodeEvent) => void,
  signal: AbortSignal
): Promise<ChatResponse> => {
  const [url, init] = buildRequest(question, image, signal);
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === 'AbortError') throw exc;
    throw new ApiError('network error', 0);
  }
  if (!res.ok) throw await errorFromResponse(res);
  if (!res.body) throw new ApiError('stream ended without an answer', 0);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n?/g, '\n');
    const frames = buffer.split('\n\n');
    buffer = frames.pop() ?? '';
    for (const frame of frames) {
      const parsed = parseFrame(frame);
      if (!parsed) continue;
      const payload = JSON.parse(parsed.data);
      if (parsed.event === 'node') onNode(payload as NodeEvent);
      else if (parsed.event === 'final') return payload as ChatResponse;
      else if (parsed.event === 'error') {
        throw new ApiError(payload.error ?? 'stream failed', 0, payload.request_id ?? null);
      }
    }
  }
  throw new ApiError('stream ended without an answer', 0);
};
