export interface SourceInfo {
  document_id?: string;
  chunk_id?: string;
  title: string;
  source_type?: string;
  file_path?: string;
  score?: number;
  score_bm25?: number;
  score_vector?: number;
  preview?: string;
}

export interface ChatEvent {
  type: 'token' | 'sources' | 'done' | 'error';
  data: string;
  sources?: SourceInfo[];
}

export async function* streamChat(question: string): AsyncGenerator<ChatEvent> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api';

  const response = await fetch(`${baseUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, stream: true }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';
  let currentEvent = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
        continue;
      }

      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (!data || data === '[DONE]') {
          yield { type: 'done', data: '' };
          currentEvent = '';
          continue;
        }

        try {
          const parsed = JSON.parse(data);

          if (currentEvent === 'token' || parsed.content !== undefined) {
            yield { type: 'token', data: parsed.content ?? '' };
          } else if (currentEvent === 'sources' || parsed.sources) {
            yield { type: 'sources', data: '', sources: parsed.sources };
          } else if (currentEvent === 'done') {
            yield { type: 'done', data: '' };
          } else if (parsed.error) {
            yield { type: 'error', data: parsed.error };
          } else if (parsed.answer) {
            yield { type: 'token', data: parsed.answer };
          }
        } catch {
          // Plain text token
          yield { type: 'token', data };
        }

        currentEvent = '';
      }
    }
  }
}

export async function sendChatMessage(question: string): Promise<{ answer: string; sources: SourceInfo[] }> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api';

  const response = await fetch(`${baseUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, stream: false }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  return response.json();
}
